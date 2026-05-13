from __future__ import annotations

import asyncio
import inspect
import json
import os
import platform
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Any
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, Signal

from ..domain.agent_message import AgentMessage, TextBlock, ToolCallBlock, ToolResultBlock
from ..domain.block import Block
from .agent_tools import TOOL_REGISTRY, AgentTool, ToolResult


# ── agent step (streamed to UI) ───────────────────────────────────────────────

@dataclass
class AgentStep:
    type: str   # "text_delta" | "tool_call" | "tool_call_start" | "tool_call_end" | "turn_complete" | "error"
    data: Any = None


# ── system prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(cwd: str) -> str:
    shell = os.environ.get("SHELL", "bash")
    home  = str(Path.home())
    try:
        entries    = sorted(os.listdir(cwd))[:20]
        dir_lines  = "\n".join(
            f"  {'/' if os.path.isdir(os.path.join(cwd, e)) else ''}{e}"
            for e in entries
        )
    except OSError:
        dir_lines = "  (unreadable)"

    return f"""You are a terminal assistant embedded in Blocksh, a block-based terminal emulator.

## Environment
- OS: {platform.system()} {platform.release()}
- Shell: {shell}
- Working directory: {cwd}
- Home: {home}

## Current directory
{dir_lines}

## Tools
- **inspect_project(path)** — Best first tool for any project/folder. Detects type, lists files, reads key metadata (README, config) in one call. Also works for single files.
- **read_file(path, start_line, end_line)** — Read a specific *file*. Do NOT call on directories — use inspect_project or list_dir instead.
- **list_dir(path)** — List a directory's contents.
- **search_files(pattern, path, file_glob)** — Search inside files.
- **run_command(command)** — Run a shell command (requires user approval).
- **ask_user(question)** — Ask the user for clarification.

## Tool usage rules (follow strictly)
1. When a path could be a directory → call **inspect_project** first.
2. Never call read_file on a directory; it will fail and waste a turn.
3. For project inspection: inspect_project → read additional files if needed → synthesize.
4. Always end with a natural-language summary for the user; do not let tool output be your final answer.
5. If a path does not exist, say so clearly and stop.

## Response style
- Be concise and developer-focused
- Use markdown: **bold**, `code`, fenced code blocks with language tags
- For errors: show the exact fix, not just the diagnosis
- If producing a shell command for the user, put it on its own line starting with CMD:
"""


# ── message converters ────────────────────────────────────────────────────────

def _msgs_to_anthropic(messages: list[AgentMessage]) -> list[dict]:
    out: list[dict] = []
    for msg in messages:
        if msg.role == "user":
            tool_results = [b for b in msg.content if isinstance(b, ToolResultBlock)]
            text_blocks  = [b for b in msg.content if isinstance(b, TextBlock)]
            if tool_results:
                out.append({
                    "role": "user",
                    "content": [
                        {
                            "type":        "tool_result",
                            "tool_use_id": b.tool_call_id,
                            "content":     b.content,
                            "is_error":    b.is_error,
                        }
                        for b in tool_results
                    ],
                })
            if text_blocks:
                out.append({"role": "user", "content": "\n".join(b.text for b in text_blocks)})
        elif msg.role == "assistant":
            content: list[dict] = []
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text:
                    content.append({"type": "text", "text": block.text})
                elif isinstance(block, ToolCallBlock):
                    content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.args})
            if content:
                out.append({"role": "assistant", "content": content})
    return out


def _msgs_to_ollama(messages: list[AgentMessage], system: str) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    for msg in messages:
        if msg.role == "user":
            tool_results = [b for b in msg.content if isinstance(b, ToolResultBlock)]
            text_blocks  = [b for b in msg.content if isinstance(b, TextBlock)]
            for b in tool_results:
                out.append({"role": "tool", "content": b.content, "tool_call_id": b.tool_call_id})
            if text_blocks:
                out.append({"role": "user", "content": "\n".join(b.text for b in text_blocks)})
        elif msg.role == "assistant":
            text  = "\n".join(b.text for b in msg.content if isinstance(b, TextBlock))
            calls = [
                {
                    "id":       b.id,
                    "type":     "function",
                    "function": {"name": b.name, "arguments": b.args},
                }
                for b in msg.content if isinstance(b, ToolCallBlock)
            ]
            entry: dict = {"role": "assistant", "content": text or ""}
            if calls:
                entry["tool_calls"] = calls
            out.append(entry)
    return out


def _msgs_to_openai(messages: list[AgentMessage], system: str) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    for msg in messages:
        if msg.role == "user":
            tool_results = [b for b in msg.content if isinstance(b, ToolResultBlock)]
            text_blocks  = [b for b in msg.content if isinstance(b, TextBlock)]
            for b in tool_results:
                out.append({"role": "tool", "tool_call_id": b.tool_call_id, "content": b.content})
            if text_blocks:
                out.append({"role": "user", "content": "\n".join(b.text for b in text_blocks)})
        elif msg.role == "assistant":
            text  = "\n".join(b.text for b in msg.content if isinstance(b, TextBlock))
            calls = [
                {
                    "id":       b.id,
                    "type":     "function",
                    "function": {"name": b.name, "arguments": json.dumps(b.args)},
                }
                for b in msg.content if isinstance(b, ToolCallBlock)
            ]
            entry: dict = {"role": "assistant", "content": text}
            if calls:
                entry["tool_calls"] = calls
            out.append(entry)
    return out


# ── backends ──────────────────────────────────────────────────────────────────

class BaseBackend:
    async def stream(
        self,
        messages: list[AgentMessage],
        system: str,
        tools: list[AgentTool],
    ) -> AsyncGenerator[AgentStep, None]:
        raise NotImplementedError

    async def complete(self, prompt: str) -> str:
        raise NotImplementedError


class _AnthropicBackend(BaseBackend):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model   = model

    async def complete(self, prompt: str) -> str:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        msg = await client.messages.create(
            model=self._model, max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    async def stream(self, messages, system, tools) -> AsyncGenerator[AgentStep, None]:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        anthropic_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in tools
        ]
        async with client.messages.stream(
            model=self._model, max_tokens=4096, system=system,
            messages=_msgs_to_anthropic(messages),
            tools=anthropic_tools,
        ) as s:
            async for text in s.text_stream:
                yield AgentStep("text_delta", text)
            final = await s.get_final_message()
            for block in final.content:
                if block.type == "tool_use":
                    yield AgentStep("tool_call", {"id": block.id, "name": block.name, "args": block.input})


class _OllamaBackend(BaseBackend):
    def __init__(self, host: str, model: str) -> None:
        self._host  = host.rstrip("/")
        self._model = model

    async def complete(self, prompt: str) -> str:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self._host}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=60.0,
            )
            r.raise_for_status()
            return r.json()["response"]

    async def stream(self, messages, system, tools) -> AsyncGenerator[AgentStep, None]:
        import httpx
        ollama_tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]
        payload = {
            "model":    self._model,
            "messages": _msgs_to_ollama(messages, system),
            "tools":    ollama_tools,
            "stream":   True,
        }
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", f"{self._host}/api/chat", json=payload, timeout=120.0) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = data.get("message", {})
                    if delta.get("content"):
                        yield AgentStep("text_delta", delta["content"])
                    for i, tc in enumerate(delta.get("tool_calls") or []):
                        fn   = tc.get("function", {})
                        args = fn.get("arguments", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {"raw": args}
                        yield AgentStep("tool_call", {
                            "id":   tc.get("id") or f"ollama_{i}_{uuid4().hex[:6]}",
                            "name": fn.get("name", ""),
                            "args": args,
                        })


class _OllamaPingBackend:
    def complete(self, _: str) -> str:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx not installed")
        httpx.get(self._host, timeout=5.0).raise_for_status()
        return "ok"

    def __init__(self, host: str) -> None:
        self._host = host.rstrip("/")


class _OpenAiBackend(BaseBackend):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model   = model

    async def complete(self, prompt: str) -> str:
        import openai
        client = openai.AsyncOpenAI(api_key=self._api_key)
        r = await client.chat.completions.create(
            model=self._model, max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content

    async def stream(self, messages, system, tools) -> AsyncGenerator[AgentStep, None]:
        import openai
        client = openai.AsyncOpenAI(api_key=self._api_key)
        oai_tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]
        tc_buffers: dict[int, dict] = {}
        stream = await client.chat.completions.create(
            model=self._model, max_tokens=4096,
            messages=_msgs_to_openai(messages, system),
            tools=oai_tools, stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield AgentStep("text_delta", delta.content)
            for tc in (delta.tool_calls or []):
                idx = tc.index
                if idx not in tc_buffers:
                    tc_buffers[idx] = {"id": "", "name": "", "args": ""}
                if tc.id:
                    tc_buffers[idx]["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        tc_buffers[idx]["name"] = tc.function.name
                    if tc.function.arguments:
                        tc_buffers[idx]["args"] += tc.function.arguments
        for idx in sorted(tc_buffers.keys()):
            buf = tc_buffers[idx]
            try:
                args = json.loads(buf["args"]) if buf["args"] else {}
            except json.JSONDecodeError:
                args = {"raw": buf["args"]}
            yield AgentStep("tool_call", {"id": buf["id"] or f"oai_{idx}", "name": buf["name"], "args": args})


# ── tool execution ────────────────────────────────────────────────────────────

async def _exec_tool(
    tc: ToolCallBlock,
    cwd: str,
    permission_cb,   # callable(str) -> bool  (blocking, runs in thread)
    ask_cb,          # callable(str) -> str   (blocking, runs in thread)
) -> ToolResultBlock:
    tool = TOOL_REGISTRY.get(tc.name)
    if tool is None:
        return ToolResultBlock(tool_call_id=tc.id, content=f"Unknown tool: {tc.name}", is_error=True)

    args = {**tc.args, "cwd": cwd}

    if tc.name == "run_command":
        if permission_cb is None:
            return ToolResultBlock(tool_call_id=tc.id, content="run_command not available (no permission callback).", is_error=True)
        granted = await asyncio.to_thread(permission_cb, args.get("command", ""))
        if not granted:
            return ToolResultBlock(tool_call_id=tc.id, content="User denied permission.", is_error=False)

    if tc.name == "ask_user":
        if ask_cb is None:
            return ToolResultBlock(tool_call_id=tc.id, content="ask_user not available.", is_error=True)
        question = args.get("question", "")
        answer   = await asyncio.to_thread(ask_cb, question)
        return ToolResultBlock(tool_call_id=tc.id, content=answer or "(no answer)", is_error=False)

    try:
        sig   = inspect.signature(tool.call)
        valid = {k: v for k, v in args.items() if k in sig.parameters}
        result = await asyncio.to_thread(tool.call, **valid)
    except Exception as exc:
        return ToolResultBlock(tool_call_id=tc.id, content=f"Tool error: {exc}", is_error=True)

    return ToolResultBlock(tool_call_id=tc.id, content=result.content, is_error=result.is_error)


# ── AgentSession ──────────────────────────────────────────────────────────────

_MAX_TURNS      = 30
_MAX_TOOL_CALLS = 12   # hard cap per session turn to prevent runaway loops


class AgentSession:
    """Persistent multi-turn conversation session."""

    def __init__(self, backend: BaseBackend, cwd: str) -> None:
        self._backend  = backend
        self._cwd      = cwd
        self._messages: list[AgentMessage] = []
        self._system   = _build_system_prompt(cwd)
        self.session_id = str(uuid4())

    def update_cwd(self, cwd: str) -> None:
        self._cwd   = cwd
        self._system = _build_system_prompt(cwd)

    def clear(self) -> None:
        self._messages.clear()

    @property
    def messages(self) -> list[AgentMessage]:
        return list(self._messages)

    async def send(
        self,
        user_text: str,
        permission_cb=None,
        ask_cb=None,
    ) -> AsyncGenerator[AgentStep, None]:
        self._messages.append(
            AgentMessage(role="user", content=[TextBlock(text=user_text)])
        )

        total_tool_calls = 0
        seen_calls: set[tuple] = set()  # (name, stable_args_repr) — dedup guard

        for _ in range(_MAX_TURNS):
            assistant_msg = AgentMessage(role="assistant")
            tool_calls:  list[ToolCallBlock] = []

            async for chunk in self._backend.stream(
                self._messages, self._system, list(TOOL_REGISTRY.values())
            ):
                if chunk.type == "text_delta":
                    if (not assistant_msg.content or
                            not isinstance(assistant_msg.content[-1], TextBlock)):
                        assistant_msg.content.append(TextBlock(text=""))
                    assistant_msg.content[-1].text += chunk.data
                    yield chunk
                elif chunk.type == "tool_call":
                    tc = ToolCallBlock(
                        id=chunk.data["id"],
                        name=chunk.data["name"],
                        args=chunk.data["args"],
                    )
                    assistant_msg.content.append(tc)
                    tool_calls.append(tc)
                    yield AgentStep("tool_call_start", {"name": tc.name, "args": tc.args})

            self._messages.append(assistant_msg)

            if not tool_calls:
                yield AgentStep("turn_complete")
                return

            result_blocks: list[ToolResultBlock] = []
            for tc in tool_calls:
                call_key = (tc.name, json.dumps(tc.args, sort_keys=True, default=str))

                if total_tool_calls >= _MAX_TOOL_CALLS:
                    rb = ToolResultBlock(
                        tool_call_id=tc.id,
                        content="Tool call limit reached. Please synthesise findings and answer the user now.",
                        is_error=True,
                    )
                elif call_key in seen_calls:
                    rb = ToolResultBlock(
                        tool_call_id=tc.id,
                        content=f"Duplicate call: {tc.name} with the same arguments was already executed. Use the previous result.",
                        is_error=True,
                    )
                else:
                    seen_calls.add(call_key)
                    total_tool_calls += 1
                    rb = await _exec_tool(tc, self._cwd, permission_cb, ask_cb)

                result_blocks.append(rb)
                yield AgentStep("tool_call_end", {
                    "name":     tc.name,
                    "result":   rb.content[:200],
                    "is_error": rb.is_error,
                })

            self._messages.append(
                AgentMessage(role="user", content=result_blocks)
            )

        yield AgentStep("error", "Maximum reasoning steps reached.")


# ── one-shot worker (explain / fix / translate) ───────────────────────────────

class _AiWorker(QThread):
    result_ready   = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, prompt: str, backend) -> None:
        super().__init__()
        self._prompt  = prompt
        self._backend = backend

    def run(self) -> None:
        try:
            if asyncio.iscoroutinefunction(getattr(self._backend, "complete", None)):
                result = asyncio.run(self._backend.complete(self._prompt))
            else:
                result = self._backend.complete(self._prompt)
            self.result_ready.emit(result.strip())
        except Exception as exc:
            self.error_occurred.emit(str(exc))


# ── agent worker (multi-turn streaming) ──────────────────────────────────────

def _args_preview(args: dict) -> str:
    if not args:
        return ""
    if len(args) == 1:
        return str(next(iter(args.values())))
    return ", ".join(f"{k}={v}" for k, v in args.items())


class AgentWorker(QThread):
    text_delta        = Signal(str)
    tool_call_start   = Signal(str, str)         # name, args_preview
    tool_call_end     = Signal(str, str, bool)   # name, result_preview, is_error
    turn_complete     = Signal()
    permission_needed = Signal(str)              # command needing approval
    user_asked        = Signal(str)              # question from ask_user tool
    command_ready     = Signal(str)              # CMD: line for InputBar
    final_answer      = Signal(str)              # full accumulated text (backward compat)
    error_occurred    = Signal(str)

    # backward-compat aliases
    tool_called       = Signal(str, str)         # same as tool_call_start
    tool_result_ready = Signal(str, str, str)    # name, args_preview, result_preview
    ask_user          = Signal(str)              # same as user_asked

    _PERM_TIMEOUT = 120

    def __init__(self, session: AgentSession, request: str) -> None:
        super().__init__()
        self._session    = session
        self._request    = request
        self._perm_event = threading.Event()
        self._perm_ok    = False
        self._ask_event  = threading.Event()
        self._ask_answer = ""
        self._cancelled  = False
        self._full_text  = ""

    def grant_permission(self, allowed: bool) -> None:
        self._perm_ok = allowed
        self._perm_event.set()

    def answer_question(self, answer: str) -> None:
        self._ask_answer = answer
        self._ask_event.set()

    def cancel(self) -> None:
        self._cancelled = True
        self._perm_event.set()
        self._ask_event.set()

    # ── sync callbacks (run in thread-pool via asyncio.to_thread) ─────────────

    def _permission_cb(self, command: str) -> bool:
        if self._cancelled:
            return False
        self._perm_event.clear()
        self._perm_ok = False
        self.permission_needed.emit(command)
        if not self._perm_event.wait(timeout=self._PERM_TIMEOUT):
            return False
        return not self._cancelled and self._perm_ok

    def _ask_cb(self, question: str) -> str:
        if self._cancelled:
            return ""
        self._ask_event.clear()
        self._ask_answer = ""
        self.user_asked.emit(question)
        self.ask_user.emit(question)
        if not self._ask_event.wait(timeout=self._PERM_TIMEOUT):
            return "Timeout"
        return self._ask_answer

    # ── thread entry ──────────────────────────────────────────────────────────

    def run(self) -> None:
        try:
            asyncio.run(self._async_loop())
        except Exception as exc:
            if not self._cancelled:
                self.error_occurred.emit(str(exc))

    async def _async_loop(self) -> None:
        try:
            async for step in self._session.send(
                self._request,
                permission_cb=self._permission_cb,
                ask_cb=self._ask_cb,
            ):
                if self._cancelled:
                    return

                if step.type == "text_delta":
                    self._full_text += step.data
                    self.text_delta.emit(step.data)

                elif step.type == "tool_call_start":
                    name    = step.data["name"]
                    preview = _args_preview(step.data["args"])
                    self.tool_call_start.emit(name, preview)
                    self.tool_called.emit(name, preview)

                elif step.type == "tool_call_end":
                    name    = step.data["name"]
                    preview = step.data["result"]
                    is_err  = step.data["is_error"]
                    self.tool_call_end.emit(name, preview, is_err)
                    self.tool_result_ready.emit(name, "", preview)

                elif step.type == "turn_complete":
                    self.turn_complete.emit()
                    text      = self._full_text.strip()
                    cmd_match = re.search(r"^CMD:\s*(.+)$", text, re.MULTILINE)
                    if cmd_match:
                        self.command_ready.emit(cmd_match.group(1).strip())
                    else:
                        self.final_answer.emit(text or "(no response)")
                    return

                elif step.type == "error":
                    self.error_occurred.emit(str(step.data))
                    return

        except Exception as exc:
            if not self._cancelled:
                self.error_occurred.emit(str(exc))


# ── AiService singleton ───────────────────────────────────────────────────────

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

    def create_session(self, cwd: str) -> AgentSession:
        return AgentSession(self._get_backend(), cwd)

    def agent_chat(self, session: AgentSession, request: str) -> AgentWorker:
        return AgentWorker(session, request)

    def _get_backend(self) -> BaseBackend:
        from .settings_service import SettingsService
        s = SettingsService.instance().get()
        if s.ai_backend == "anthropic":
            return _AnthropicBackend(s.ai_anthropic_key, s.ai_anthropic_model)
        if s.ai_backend == "openai":
            return _OpenAiBackend(s.ai_openai_key, s.ai_openai_model)
        return _OllamaBackend(s.ai_ollama_host, s.ai_ollama_model)
