import os
import subprocess
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Module-level cache: the login-shell environment is captured once and reused
# for every new tab, avoiding repeated subprocess spawns.
_login_env_cache: dict[str, str] | None = None


def _capture_login_env() -> dict[str, str]:
    """
    Run the user's login shell non-interactively and capture its environment.

    This gives Blocksh the same PATH (and other variables) that the user sees
    in a real terminal — including paths added by .bashrc, .zshrc, nvm, cargo,
    bun, etc. — without requiring any user configuration.

    Falls back to os.environ silently if the shell cannot be spawned within
    the timeout, so the app never blocks at startup.

    The result is cached at module level — every new tab reuses the same
    snapshot rather than spawning another subprocess.
    """
    global _login_env_cache
    if _login_env_cache is not None:
        return _login_env_cache.copy()

    shell = os.environ.get("SHELL", "/bin/bash")
    try:
        result = subprocess.run(
            [shell, "-lic", "env"],
            capture_output=True,
            text=True,
            timeout=3,
            # Detach from any controlling terminal so the shell starts cleanly
            start_new_session=True,
        )
        if result.returncode != 0 and not result.stdout:
            return os.environ.copy()

        env: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key.isidentifier():
                env[key] = value
        _login_env_cache = env if env else os.environ.copy()
        return _login_env_cache.copy()

    except Exception as exc:
        log.debug("_capture_login_env failed (%s) — falling back to os.environ", exc)
        _login_env_cache = os.environ.copy()
        return _login_env_cache.copy()


class ShellSession:
    """
    Tracks the logical state of the terminal session (cwd, env vars).

    Because subprocess runs in a child process, shell built-ins like `cd`
    don't propagate back to Python. This class mirrors that state manually
    so subsequent commands run in the correct directory.

    The initial environment is captured from the user's login shell so that
    tools installed in ~/.local/bin, ~/.cargo/bin, ~/.nvm/…/bin, etc. are
    always discoverable, matching the behaviour of a real terminal.
    """

    def __init__(self, initial_cwd: str | None = None, env: dict[str, str] | None = None):
        self._cwd = initial_cwd or os.getcwd()
        # If a pre-captured env is provided (e.g. from app startup) use it;
        # otherwise capture now (useful for tests / isolated instantiation).
        self._env: dict[str, str] = env if env is not None else _capture_login_env()

    @property
    def cwd(self) -> str:
        return self._cwd

    @property
    def env(self) -> dict[str, str]:
        return self._env.copy()

    def cwd_display(self) -> str:
        """Returns cwd with the home directory replaced by ~."""
        home = str(Path.home())
        if self._cwd == home:
            return "~"
        if self._cwd.startswith(home + "/"):
            return "~" + self._cwd[len(home):]
        return self._cwd

    def try_cd(self, command_text: str) -> bool:
        """
        If the command is a `cd` invocation, resolves the target path and
        updates the internal cwd. Returns True when cwd was updated.

        Handles: cd, cd ~, cd /abs/path, cd relative/path, cd ~/subdir.
        Does not handle: cd - (previous dir), env var expansion, globbing.
        """
        stripped = command_text.strip()

        # bare `cd` goes home
        if stripped == "cd":
            self._cwd = str(Path.home())
            return True

        if not (stripped.startswith("cd ") or stripped.startswith("cd\t")):
            return False

        arg = stripped[2:].strip().strip("'\"")

        if not arg or arg == "~":
            self._cwd = str(Path.home())
            return True

        if arg.startswith("~/"):
            target = Path.home() / arg[2:]
        elif arg.startswith("/"):
            target = Path(arg)
        else:
            target = Path(self._cwd) / arg

        resolved = target.resolve()
        if resolved.is_dir():
            self._cwd = str(resolved)
            return True

        return False  # directory doesn't exist — let subprocess report the error

    # ── .env file support ─────────────────────────────────────────────────

    def detect_env_files(self) -> list[Path]:
        """Return existing .env* files in current cwd, in priority order."""
        candidates = [".env.local", ".env.development", ".env"]
        return [
            Path(self._cwd) / name
            for name in candidates
            if (Path(self._cwd) / name).exists()
        ]

    def load_env_file(self, path: Path) -> dict[str, str]:
        """Parse a .env file and return key=value pairs.
        Skips comments (#) and blank lines. Strips quotes from values."""
        result: dict[str, str] = {}
        try:
            for line in path.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key   = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    result[key] = value
        except Exception:
            pass
        return result

    def apply_env(self, variables: dict[str, str]) -> None:
        """Merge variables into this session's environment."""
        self._env.update(variables)
