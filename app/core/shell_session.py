import os
from pathlib import Path


class ShellSession:
    """
    Tracks the logical state of the terminal session (cwd, env vars).

    Because subprocess runs in a child process, shell built-ins like `cd`
    don't propagate back to Python. This class mirrors that state manually
    so subsequent commands run in the correct directory.
    """

    def __init__(self, initial_cwd: str | None = None):
        self._cwd = initial_cwd or os.getcwd()
        self._env: dict[str, str] = os.environ.copy()

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
