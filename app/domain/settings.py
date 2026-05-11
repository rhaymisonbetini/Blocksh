from dataclasses import dataclass


@dataclass
class AppSettings:
    font_family: str = "Monospace"
    font_size_terminal: int = 10
    font_size_output: int = 9
    cursor_style: str = "block"       # block | underline | beam
    output_fg_override: str = ""      # empty = use theme palette.fg
    default_shell: str = "bash"
    scrollback_lines: int = 2000
    history_limit: int = 200
    auto_scroll: bool = True
    history_retention_days: int = 0   # 0 = keep forever
    avatar_path: str = ""             # absolute path to profile photo
    ai_enabled:         bool = True
    ai_backend:         str  = "ollama"
    ai_ollama_host:     str  = "http://localhost:11434"
    ai_ollama_model:    str  = "qwen2.5-coder:1.5b"
    ai_anthropic_key:   str  = ""
    ai_anthropic_model: str  = "claude-haiku-4-5-20251001"
    ai_openai_key:      str  = ""
    ai_openai_model:    str  = "gpt-4o-mini"
    auto_load_env:      str  = "ask"   # "ask" | "always" | "never"
