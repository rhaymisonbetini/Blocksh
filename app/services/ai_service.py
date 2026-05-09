from __future__ import annotations

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
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model   = model

    def complete(self, prompt: str) -> str:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic not installed — run: pip install anthropic")
        client = anthropic.Anthropic(api_key=self._api_key)
        msg = client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text


class _OpenAiBackend:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model   = model

    def complete(self, prompt: str) -> str:
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai not installed — run: pip install openai")
        client = openai.OpenAI(api_key=self._api_key)
        r = client.chat.completions.create(
            model=self._model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content


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

    def _get_backend(self):
        from .settings_service import SettingsService
        s = SettingsService.instance().get()
        if s.ai_backend == "anthropic":
            return _AnthropicBackend(s.ai_anthropic_key, s.ai_anthropic_model)
        if s.ai_backend == "openai":
            return _OpenAiBackend(s.ai_openai_key, s.ai_openai_model)
        return _OllamaBackend(s.ai_ollama_host, s.ai_ollama_model)
