from __future__ import annotations

import os
import re
import subprocess
import threading

from PySide6.QtCore import QObject, QThread, Signal

from ..domain.block import Block


class _AiWorker(QThread):
    result_ready   = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, prompt: str, backend) -> None:
        super().__init__()
        self._prompt  = prompt
        self._backend = backend

    def run(self) -> None:
        try:
            result = self._backend.complete(self._prompt)
            self.result_ready.emit(result.strip())
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class _OllamaBackend:
    def __init__(self, host: str, model: str) -> None:
        self._host  = host.rstrip("/")
        self._model = model

    def complete(self, prompt: str) -> str:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx not installed — run: pip install httpx")
        r = httpx.post(
            f"{self._host}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()["response"]


class _OllamaPingBackend:
    def __init__(self, host: str) -> None:
        self._host = host.rstrip("/")

    def complete(self, _: str) -> str:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx not installed")
        httpx.get(self._host, timeout=5.0).raise_for_status()
        return "ok"


class _AnthropicBackend:
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024) -> None:
        self._api_key    = api_key
        self._model      = model
        self._max_tokens = max_tokens

    def complete(self, prompt: str) -> str:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic not installed — run: pip install anthropic")
        client = anthropic.Anthropic(api_key=self._api_key)
        msg = client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text


class _OpenAiBackend:
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024) -> None:
        self._api_key    = api_key
        self._model      = model
        self._max_tokens = max_tokens

    def complete(self, prompt: str) -> str:
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai not installed — run: pip install openai")
        client = openai.OpenAI(api_key=self._api_key)
        r = client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content


_SYSTEM_PROMPT = """\
You are a terminal assistant with read access to the filesystem.
Working directory: {cwd}

You can use these tools by including them EXACTLY as shown in your response:
  [READ: /path/to/file]    — read a file (no permission needed)
  [LIST: /path/to/dir]     — list a directory (no permission needed)
  [RUN: shell command]     — run a command (user must approve first)

Rules:
1. Use at most ONE tool per response. You will receive the result in the next message.
2. Relative paths are resolved from the working directory shown above.
3. Once you have enough information, write your final answer.
4. If the final answer IS a shell command the user should run, prefix it with CMD: on its own line.
   Example: CMD: grep -r "TODO" .
5. Otherwise write a plain text answer. Be concise and developer-focused.
6. Never make up file contents — always use [READ:] if you need to see a file."""


class AgentWorker(QThread):
    tool_called       = Signal(str, str)        # tool_name, argument
    tool_result_ready = Signal(str, str, str)   # tool_name, argument, short_preview
    permission_needed = Signal(str)             # command string waiting for approval
    final_answer      = Signal(str)             # plain-text answer to show inline
    command_ready     = Signal(str)             # shell command → put in InputBar
    error_occurred    = Signal(str)

    _MAX_TURNS      = 10
    _MAX_FILE_BYTES = 10_000
    _MAX_LIST_ITEMS = 60
    _PERM_TIMEOUT   = 120  # seconds

    def __init__(self, request: str, cwd: str, backend) -> None:
        super().__init__()
        self._request  = request
        self._cwd      = cwd
        self._backend  = backend
        self._perm_event   = threading.Event()
        self._perm_granted = False
        self._cancelled    = False

    def grant_permission(self, allowed: bool) -> None:
        self._perm_granted = allowed
        self._perm_event.set()

    def cancel(self) -> None:
        self._cancelled = True
        self._perm_event.set()

    def run(self) -> None:
        try:
            self._loop()
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def _loop(self) -> None:
        system = _SYSTEM_PROMPT.format(cwd=self._cwd)
        history: list[str] = [f"{system}\n\nUser request: {self._request}"]

        for _ in range(self._MAX_TURNS):
            if self._cancelled:
                return

            response = self._backend.complete("\n\n".join(history)).strip()

            # Final shell command?
            cmd_match = re.search(r'^CMD:\s*(.+)$', response, re.MULTILINE)
            if cmd_match:
                self.command_ready.emit(cmd_match.group(1).strip())
                return

            # Tool call?
            tool_match = re.search(r'\[(READ|LIST|RUN):\s*(.+?)\]', response, re.IGNORECASE)
            if not tool_match:
                self.final_answer.emit(response)
                return

            tool = tool_match.group(1).upper()
            arg  = tool_match.group(2).strip()
            self.tool_called.emit(tool, arg)

            result = self._execute_tool(tool, arg)
            if result is None:
                history.append(response)
                history.append("[Tool result: User denied permission.]")
            else:
                preview = result[:120].replace("\n", " ") + ("…" if len(result) > 120 else "")
                self.tool_result_ready.emit(tool, arg, preview)
                history.append(response)
                history.append(f"[Tool result for {tool}({arg}):\n{result}\n]")

        self.error_occurred.emit("Reached maximum reasoning steps without a final answer.")

    def _execute_tool(self, tool: str, arg: str) -> str | None:
        if tool == "READ":
            return self._read_file(arg)
        if tool == "LIST":
            return self._list_dir(arg)
        if tool == "RUN":
            return self._run_with_permission(arg)
        return f"Unknown tool: {tool}"

    def _abs(self, path: str) -> str:
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.join(self._cwd, path)
        return path

    def _read_file(self, path: str) -> str:
        full = self._abs(path)
        try:
            with open(full, "rb") as fh:
                raw = fh.read(self._MAX_FILE_BYTES)
            text = raw.decode("utf-8", errors="replace")
            size = os.path.getsize(full)
            if size > self._MAX_FILE_BYTES:
                text += f"\n… [showing first {self._MAX_FILE_BYTES} of {size} bytes]"
            return text
        except Exception as exc:
            return f"Error reading file: {exc}"

    def _list_dir(self, path: str) -> str:
        full = self._abs(path)
        try:
            entries = sorted(os.listdir(full))[: self._MAX_LIST_ITEMS]
            lines = []
            for name in entries:
                fp = os.path.join(full, name)
                if os.path.isdir(fp):
                    lines.append(f"{name}/")
                else:
                    try:
                        sz = os.path.getsize(fp)
                        lines.append(f"{name}  ({sz:,} bytes)")
                    except OSError:
                        lines.append(name)
            total = len(os.listdir(full))
            suffix = f"\n… ({total - self._MAX_LIST_ITEMS} more)" if total > self._MAX_LIST_ITEMS else ""
            return ("\n".join(lines) or "(empty directory)") + suffix
        except Exception as exc:
            return f"Error listing directory: {exc}"

    def _run_with_permission(self, command: str) -> str | None:
        self._perm_event.clear()
        self._perm_granted = False
        self.permission_needed.emit(command)

        if not self._perm_event.wait(timeout=self._PERM_TIMEOUT):
            return "Timeout — no response from user."
        if self._cancelled or not self._perm_granted:
            return None

        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=30, cwd=self._cwd,
            )
            output = (proc.stdout + proc.stderr).strip() or "(no output)"
            if len(output) > 3000:
                output = output[:3000] + "\n… [truncated]"
            return output
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."
        except Exception as exc:
            return f"Error running command: {exc}"


class AiService(QObject):
    _instance: AiService | None = None

    @classmethod
    def instance(cls) -> AiService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_enabled(self) -> bool:
        from .settings_service import SettingsService
        return SettingsService.instance().get().ai_enabled

    def explain(self, block: Block) -> _AiWorker:
        output = (block.stdout or block.stderr or "").strip()
        prompt = (
            f"You are a terminal assistant. The user ran this command in {block.cwd}:\n\n"
            f"Command: {block.command.text}\n"
            f"Output:\n{output}\n\n"
            "Explain briefly (3-5 sentences) what this command does and what the output means. "
            "Be concise and developer-focused."
        )
        return _AiWorker(prompt, self._get_backend())

    def fix(self, block: Block) -> _AiWorker:
        prompt = (
            "You are a shell expert. This command failed:\n\n"
            f"Command: {block.command.text}\n"
            f"Directory: {block.cwd}\n"
            f"Error:\n{block.stderr}\n"
            f"Exit code: {block.exit_code}\n\n"
            "Return ONLY the corrected shell command, nothing else. No explanation, no markdown."
        )
        return _AiWorker(prompt, self._get_backend())

    def agent_chat(self, request: str, cwd: str) -> AgentWorker:
        return AgentWorker(request, cwd, self._get_backend())

    def translate(self, text: str, cwd: str) -> _AiWorker:
        prompt = (
            "You are a shell expert. Convert this request to a single shell command.\n"
            f"Working directory: {cwd}\n"
            f"Request: {text}\n"
            "Return ONLY the shell command, nothing else."
        )
        return _AiWorker(prompt, self._get_backend())

    def check_ollama(self, host: str) -> _AiWorker:
        return _AiWorker("", _OllamaPingBackend(host))

    def _get_backend(self):
        from .settings_service import SettingsService
        s = SettingsService.instance().get()
        if s.ai_backend == "anthropic":
            return _AnthropicBackend(s.ai_anthropic_key, s.ai_anthropic_model)
        if s.ai_backend == "openai":
            return _OpenAiBackend(s.ai_openai_key, s.ai_openai_model)
        return _OllamaBackend(s.ai_ollama_host, s.ai_ollama_model)
