from __future__ import annotations

import json
import os
import re
import subprocess
import threading
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QThread, Signal

from ..domain.block import Block


# ── simple one-shot worker (explain / fix / translate) ────────────────────

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


# ── agent step dataclasses ────────────────────────────────────────────────

@dataclass
class ToolCall:
    id:   str
    name: str
    args: dict


@dataclass
class AgentStep:
    text:        str
    tool_calls:  list[ToolCall] = field(default_factory=list)
    raw_content: list[dict]     = field(default_factory=list)


# ── tool schemas (Anthropic format — converted per-backend in step()) ─────

_AGENT_TOOLS: list[dict] = [
    {
        "name": "read_file",
        "description": (
            "Read the contents of a file. Use exact paths as returned by list_dir. "
            "Only reads plain-text files up to 10 KB."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to cwd or absolute"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_dir",
        "description": (
            "List the contents of a directory. Returns filenames with sizes. "
            "Always call this before read_file to get the exact filename spelling."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path. Use '.' for the working directory.",
                    "default": ".",
                },
            },
        },
    },
    {
        "name": "run_command",
        "description": (
            "Run a shell command in the user's terminal. "
            "Requires explicit user approval before executing. "
            "Use only when reading files is not enough to fulfill the request."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "ask_user",
        "description": (
            "Ask the user a clarifying question when the request is ambiguous "
            "or you need more information before proceeding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The clarifying question to ask"},
            },
            "required": ["question"],
        },
    },
]

_SYSTEM_PROMPT = """\
You are a terminal assistant for the Blocksh terminal emulator.
The user is working in: {cwd}

Current directory contents:
{cwd_listing}

You have four tools: read_file, list_dir, run_command, ask_user.
- Always call list_dir first to get exact filenames before calling read_file.
- run_command requires user approval. Only use it when file reading is not enough.
- Use ask_user when the request is ambiguous or you need clarification.
- Answer in plain text. Be thorough, conversational, and developer-focused.
- If the task is to produce a shell command for the user to run, end your response with:
  CMD: <the shell command>
"""


# ── backends ──────────────────────────────────────────────────────────────

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

    def step(self, system: str, messages: list[dict], tools: list[dict]) -> AgentStep:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx not installed — run: pip install httpx")

        ollama_msgs = [{"role": "system", "content": system}]
        for msg in messages:
            ollama_msgs.extend(_canonical_to_ollama(msg))

        ollama_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

        r = httpx.post(
            f"{self._host}/api/chat",
            json={
                "model": self._model,
                "messages": ollama_msgs,
                "tools": ollama_tools,
                "stream": False,
            },
            timeout=120.0,
        )
        r.raise_for_status()
        msg = r.json()["message"]

        calls: list[ToolCall] = []
        raw_content: list[dict] = []

        if msg.get("content"):
            raw_content.append({"type": "text", "text": msg["content"]})

        for i, tc in enumerate(msg.get("tool_calls") or []):
            fn   = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            call_id = f"call_{i}"
            calls.append(ToolCall(id=call_id, name=fn.get("name", ""), args=args))
            raw_content.append({
                "type": "tool_use",
                "id": call_id,
                "name": fn.get("name", ""),
                "input": args,
            })

        return AgentStep(text=msg.get("content") or "", tool_calls=calls, raw_content=raw_content)


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

    def step(self, system: str, messages: list[dict], tools: list[dict]) -> AgentStep:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic not installed — run: pip install anthropic")
        client = anthropic.Anthropic(api_key=self._api_key)
        # Canonical messages ARE Anthropic format — pass directly.
        resp = client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=tools,
        )
        text  = ""
        calls: list[ToolCall] = []
        raw:   list[dict]     = []
        for block in resp.content:
            block_dict = block.model_dump()
            raw.append(block_dict)
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, args=block.input))
        return AgentStep(text=text, tool_calls=calls, raw_content=raw)


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

    def step(self, system: str, messages: list[dict], tools: list[dict]) -> AgentStep:
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai not installed — run: pip install openai")
        client = openai.OpenAI(api_key=self._api_key)

        oai_msgs: list[dict] = [{"role": "system", "content": system}]
        for msg in messages:
            oai_msgs.extend(_canonical_to_openai(msg))

        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

        resp   = client.chat.completions.create(
            model=self._model,
            messages=oai_msgs,
            tools=oai_tools,
            tool_choice="auto",
            max_tokens=4096,
        )
        choice = resp.choices[0]
        calls: list[ToolCall] = []
        raw_content: list[dict] = []

        if choice.message.content:
            raw_content.append({"type": "text", "text": choice.message.content})

        for tc in (choice.message.tool_calls or []):
            args = json.loads(tc.function.arguments)
            calls.append(ToolCall(id=tc.id, name=tc.function.name, args=args))
            raw_content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": args,
            })

        return AgentStep(
            text=choice.message.content or "",
            tool_calls=calls,
            raw_content=raw_content,
        )


# ── canonical ↔ backend message converters ────────────────────────────────

def _canonical_to_ollama(msg: dict) -> list[dict]:
    """Convert one canonical message to a list of Ollama messages."""
    role    = msg["role"]
    content = msg["content"]

    if role == "user":
        if isinstance(content, list):
            # Tool results
            return [
                {"role": "tool", "content": block.get("content", "")}
                for block in content
                if block.get("type") == "tool_result"
            ]
        return [{"role": "user", "content": content}]

    if role == "assistant":
        if isinstance(content, list):
            text       = ""
            tool_calls = []
            for block in content:
                if block.get("type") == "text":
                    text = block.get("text", "")
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "function": {
                            "name":      block["name"],
                            "arguments": block["input"],
                        }
                    })
            out: dict = {"role": "assistant", "content": text}
            if tool_calls:
                out["tool_calls"] = tool_calls
            return [out]
        return [{"role": "assistant", "content": content}]

    return [msg]


def _canonical_to_openai(msg: dict) -> list[dict]:
    """Convert one canonical message to a list of OpenAI messages."""
    role    = msg["role"]
    content = msg["content"]

    if role == "user":
        if isinstance(content, list):
            return [
                {
                    "role":         "tool",
                    "tool_call_id": block["tool_use_id"],
                    "content":      block.get("content", ""),
                }
                for block in content
                if block.get("type") == "tool_result"
            ]
        return [{"role": "user", "content": content}]

    if role == "assistant":
        if isinstance(content, list):
            text       = ""
            tool_calls = []
            for block in content:
                if block.get("type") == "text":
                    text = block.get("text", "")
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id":   block["id"],
                        "type": "function",
                        "function": {
                            "name":      block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    })
            out: dict = {"role": "assistant", "content": text}
            if tool_calls:
                out["tool_calls"] = tool_calls
            return [out]
        return [{"role": "assistant", "content": content}]

    return [msg]


# ── agent worker ──────────────────────────────────────────────────────────

class AgentWorker(QThread):
    tool_called       = Signal(str, str)        # tool_name, arg_preview
    tool_result_ready = Signal(str, str, str)   # tool_name, arg_preview, short_result
    permission_needed = Signal(str)             # command string waiting for approval
    ask_user          = Signal(str)             # question waiting for user reply
    final_answer      = Signal(str)             # plain-text answer to show inline
    command_ready     = Signal(str)             # shell command → put in InputBar
    error_occurred    = Signal(str)

    _MAX_TURNS      = 15
    _MAX_FILE_BYTES = 10_000
    _MAX_LIST_ITEMS = 60
    _PERM_TIMEOUT   = 120  # seconds

    def __init__(self, request: str, cwd: str, backend) -> None:
        super().__init__()
        self._request      = request
        self._cwd          = cwd
        self._backend      = backend
        self._perm_event   = threading.Event()
        self._perm_granted = False
        self._ask_event    = threading.Event()
        self._ask_answer   = ""
        self._cancelled    = False

    def grant_permission(self, allowed: bool) -> None:
        self._perm_granted = allowed
        self._perm_event.set()

    def answer_question(self, answer: str) -> None:
        self._ask_answer = answer
        self._ask_event.set()

    def cancel(self) -> None:
        self._cancelled = True
        self._perm_event.set()
        self._ask_event.set()

    def run(self) -> None:
        try:
            self._loop()
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    # ── main loop ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        system   = _SYSTEM_PROMPT.format(cwd=self._cwd, cwd_listing=self._cwd_snapshot())
        messages: list[dict] = [{"role": "user", "content": self._request}]

        for _ in range(self._MAX_TURNS):
            if self._cancelled:
                return

            step = self._backend.step(system, messages, _AGENT_TOOLS)

            # Append assistant turn to canonical history
            messages.append({"role": "assistant", "content": step.raw_content})

            if not step.tool_calls:
                text = step.text.strip()
                cmd_match = re.search(r'^CMD:\s*(.+)$', text, re.MULTILINE)
                if cmd_match:
                    self.command_ready.emit(cmd_match.group(1).strip())
                else:
                    self.final_answer.emit(text or "(no response)")
                return

            # Execute tools and collect results for the next user turn
            tool_results: list[dict] = []
            for call in step.tool_calls:
                arg_preview = _args_preview(call.args)
                self.tool_called.emit(call.name, arg_preview)

                result = self._dispatch_tool(call)
                if result is None:
                    # User denied — inform model and stop
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": call.id,
                        "content":     "User denied permission.",
                    })
                    messages.append({"role": "user", "content": tool_results})
                    self.final_answer.emit("Cancelled.")
                    return

                preview = result[:120].replace("\n", " ") + ("…" if len(result) > 120 else "")
                self.tool_result_ready.emit(call.name, arg_preview, preview)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": call.id,
                    "content":     result,
                })

            messages.append({"role": "user", "content": tool_results})

        self.error_occurred.emit("Reached maximum reasoning steps without a final answer.")

    def _dispatch_tool(self, call: ToolCall) -> str | None:
        if call.name == "read_file":
            return self._read_file(call.args.get("path", ""))
        if call.name == "list_dir":
            return self._list_dir(call.args.get("path", "."))
        if call.name == "run_command":
            return self._run_with_permission(call.args.get("command", ""))
        if call.name == "ask_user":
            return self._ask_with_permission(call.args.get("question", ""))
        return f"Unknown tool: {call.name}"

    # ── helpers ───────────────────────────────────────────────────────────

    def _cwd_snapshot(self) -> str:
        try:
            entries = sorted(os.listdir(self._cwd))[:40]
            lines   = []
            for name in entries:
                fp     = os.path.join(self._cwd, name)
                suffix = "/" if os.path.isdir(fp) else ""
                lines.append(f"  {name}{suffix}")
            total = len(os.listdir(self._cwd))
            if total > 40:
                lines.append(f"  … ({total - 40} more)")
            return "\n".join(lines)
        except Exception:
            return "  (unable to list)"

    def _abs(self, path: str) -> str:
        """Resolve path with case-insensitive fallback per component."""
        path = os.path.expanduser(path.strip())
        if not os.path.isabs(path):
            path = os.path.join(self._cwd, path)
        path = os.path.normpath(path)
        if os.path.exists(path):
            return path

        parts    = path.split(os.sep)
        resolved = os.sep
        for part in parts[1:]:
            if not part:
                continue
            exact = os.path.join(resolved, part)
            if os.path.exists(exact):
                resolved = exact
            else:
                try:
                    lower = part.lower()
                    match = next(
                        (e for e in os.listdir(resolved) if e.lower() == lower), None
                    )
                    resolved = os.path.join(resolved, match if match else part)
                except (PermissionError, NotADirectoryError, OSError):
                    resolved = os.path.join(resolved, part)
        return resolved

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
            rel_dir = os.path.relpath(full, self._cwd)
            prefix  = "" if rel_dir == "." else rel_dir.rstrip("/") + "/"

            entries = sorted(os.listdir(full))[: self._MAX_LIST_ITEMS]
            lines   = []
            for name in entries:
                fp      = os.path.join(full, name)
                display = prefix + name
                if os.path.isdir(fp):
                    lines.append(f"{display}/")
                else:
                    try:
                        sz = os.path.getsize(fp)
                        lines.append(f"{display}  ({sz:,} bytes)")
                    except OSError:
                        lines.append(display)
            total  = len(os.listdir(full))
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
            proc   = subprocess.run(
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

    def _ask_with_permission(self, question: str) -> str | None:
        self._ask_event.clear()
        self._ask_answer = ""
        self.ask_user.emit(question)
        if not self._ask_event.wait(timeout=self._PERM_TIMEOUT):
            return "Timeout — user did not reply."
        if self._cancelled:
            return None
        return self._ask_answer or "(no answer provided)"


def _args_preview(args: dict) -> str:
    """Return a compact single-value preview of tool args for UI display."""
    if not args:
        return ""
    if len(args) == 1:
        return str(next(iter(args.values())))
    return ", ".join(f"{k}={v}" for k, v in args.items())


# ── service ───────────────────────────────────────────────────────────────

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
