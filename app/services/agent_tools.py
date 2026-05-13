from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

_MAX_FILE_BYTES = 32_000
_MAX_LIST_ITEMS = 200
_MAX_CMD_BYTES  = 16_000


@dataclass
class ToolResult:
    content: str
    is_error: bool = False


@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict        # JSON Schema
    call: Callable[..., ToolResult]


# ── path helpers ──────────────────────────────────────────────────────────────

def _resolve(path: str, cwd: str) -> Path:
    p = Path(os.path.expanduser(path.strip()))
    if not p.is_absolute():
        p = Path(cwd) / p
    resolved = p.resolve()
    if resolved.exists():
        return resolved
    # Case-insensitive fallback per component
    parent = resolved.parent
    name   = resolved.name.lower()
    if parent.exists():
        match = next((f for f in parent.iterdir() if f.name.lower() == name), None)
        if match:
            return match
    return resolved


# ── tool implementations ──────────────────────────────────────────────────────

def _read_file(path: str, start_line: int = 1, end_line: int = 0, cwd: str = "") -> ToolResult:
    abs_path = _resolve(path, cwd)
    if not abs_path.exists():
        return ToolResult(f"File not found: {path}", is_error=True)
    if not abs_path.is_file():
        return ToolResult(
            f"'{abs_path}' is a directory, not a file. "
            f"Call inspect_project(path='{abs_path}') to analyse it, "
            f"or list_dir(path='{abs_path}') to see its contents.",
            is_error=True,
        )
    try:
        text  = abs_path.read_bytes().decode("utf-8", errors="replace")
        lines = text.splitlines()
        total = len(lines)

        s = max(0, start_line - 1)
        e = end_line if end_line > 0 else total
        selected = lines[s:e]

        numbered = "\n".join(f"{i + s + 1:4d} │ {l}" for i, l in enumerate(selected))

        if len(numbered.encode()) > _MAX_FILE_BYTES:
            cut   = _MAX_FILE_BYTES
            trunc = numbered[:cut]
            trunc = trunc[: trunc.rfind("\n") + 1]
            shown = trunc.count("\n") + s
            numbered = trunc + f"... [truncated at line {shown} of {total} — use start_line/end_line for ranges]"
        elif s > 0 or e < total:
            numbered = f"[lines {s + 1}–{min(e, total)} of {total}]\n" + numbered

        return ToolResult(numbered)
    except Exception as exc:
        return ToolResult(f"Error reading {path}: {exc}", is_error=True)


def _list_dir(path: str = ".", cwd: str = "") -> ToolResult:
    abs_path = _resolve(path, cwd)
    if not abs_path.exists():
        return ToolResult(f"Directory not found: {path}", is_error=True)
    if not abs_path.is_dir():
        return ToolResult(f"Not a directory: {path}", is_error=True)
    try:
        entries = sorted(abs_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        lines: list[str] = []
        for entry in entries[:_MAX_LIST_ITEMS]:
            if entry.is_dir():
                lines.append(f"{entry.name}/")
            else:
                try:
                    sz = entry.stat().st_size
                    lines.append(f"{entry.name}  ({sz:,} B)")
                except OSError:
                    lines.append(entry.name)
        total = sum(1 for _ in abs_path.iterdir())
        if total > _MAX_LIST_ITEMS:
            lines.append(f"… ({total - _MAX_LIST_ITEMS} more)")
        return ToolResult("\n".join(lines) or "(empty directory)")
    except Exception as exc:
        return ToolResult(f"Error listing {path}: {exc}", is_error=True)


def _search_files(pattern: str, path: str = ".", file_glob: str = "*", cwd: str = "") -> ToolResult:
    if not pattern:
        return ToolResult("pattern is required", is_error=True)
    abs_path = _resolve(path, cwd)
    if not abs_path.exists():
        return ToolResult(f"Path not found: {path}", is_error=True)
    try:
        rg = shutil.which("rg")
        if rg:
            cmd = [rg, "--line-number", "--no-heading", "-g", file_glob, pattern, str(abs_path)]
        else:
            cmd = ["grep", "-rn", f"--include={file_glob}", pattern, str(abs_path)]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = proc.stdout.strip()
        if not output:
            return ToolResult(f"No matches for '{pattern}' in {path}")

        result_lines = output.splitlines()
        if len(result_lines) > 200:
            output = "\n".join(result_lines[:200]) + f"\n… ({len(result_lines) - 200} more matches)"

        try:
            rel = abs_path.relative_to(Path(cwd))
            if str(rel) != ".":
                output = output.replace(str(abs_path) + os.sep, str(rel) + os.sep)
                output = output.replace(str(abs_path), str(rel))
        except ValueError:
            pass

        return ToolResult(output)
    except subprocess.TimeoutExpired:
        return ToolResult("Search timed out after 30 seconds.", is_error=True)
    except Exception as exc:
        return ToolResult(f"Search error: {exc}", is_error=True)


def _run_command(command: str, timeout: int = 30, cwd: str = "") -> ToolResult:
    if not command:
        return ToolResult("command is required", is_error=True)
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=cwd or None,
        )
        output = (proc.stdout + proc.stderr).strip() or "(no output)"
        if len(output.encode()) > _MAX_CMD_BYTES:
            output = output[:_MAX_CMD_BYTES] + "\n… [truncated]"
        return ToolResult(output, is_error=proc.returncode != 0)
    except subprocess.TimeoutExpired:
        return ToolResult(f"Command timed out after {timeout}s.", is_error=True)
    except Exception as exc:
        return ToolResult(f"Error: {exc}", is_error=True)


def _ask_user(question: str, cwd: str = "") -> ToolResult:
    # Handled specially by AgentWorker (blocking wait for user input)
    return ToolResult(question)


def _inspect_project(path: str, cwd: str = "") -> ToolResult:
    """Classify path, list directory, detect project type, and read key metadata files."""
    abs_path = _resolve(path, cwd)

    if not abs_path.exists():
        return ToolResult(f"Path not found: {path}", is_error=True)

    if abs_path.is_file():
        return _read_file(path, cwd=cwd)

    if not abs_path.is_dir():
        return ToolResult(f"Not a file or directory: {path}", is_error=True)

    try:
        all_entries = sorted(abs_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return ToolResult(f"Permission denied: {abs_path}", is_error=True)

    dirs     = [e.name for e in all_entries if e.is_dir()]
    files    = [e.name for e in all_entries if e.is_file()]
    file_set = set(files)

    lines: list[str] = [f"Path: {abs_path}", "Type: directory"]

    # --- project type detection ---
    detected: list[str] = []
    if file_set & {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"}:
        detected.append("python")
    if "package.json" in file_set:
        detected.append("node")
    if "composer.json" in file_set:
        detected.append("php")
    if "Cargo.toml" in file_set:
        detected.append("rust")
    if "go.mod" in file_set:
        detected.append("go")
    if "pom.xml" in file_set or "build.gradle" in file_set:
        detected.append("java")
    if "Gemfile" in file_set:
        detected.append("ruby")
    if any(f.endswith((".csproj", ".sln")) for f in files):
        detected.append("dotnet")
    lines.append(f"Project type: {', '.join(detected) or 'generic'}")

    # --- directory listing ---
    lines.append(f"\nDirectories ({len(dirs)}): {', '.join(dirs[:30]) or '(none)'}")
    if len(dirs) > 30:
        lines.append(f"  … and {len(dirs) - 30} more")
    lines.append(f"\nFiles ({len(files)}): {', '.join(files[:50]) or '(none)'}")
    if len(files) > 50:
        lines.append(f"  … and {len(files) - 50} more")

    # --- read key metadata files (up to 20 KB total) ---
    priority_files = [
        "README.md", "README.rst", "README.txt",
        "CLAUDE.md", "AGENTS.md",
        "pyproject.toml", "package.json", "composer.json",
        "Cargo.toml", "go.mod", "pom.xml",
        ".env.example", "Dockerfile", "docker-compose.yml", "Makefile",
    ]
    budget = 20_000
    for fname in priority_files:
        if budget <= 0:
            break
        if fname not in file_set:
            continue
        try:
            raw = (abs_path / fname).read_bytes().decode("utf-8", errors="replace").rstrip()
            if len(raw.encode()) > budget:
                raw = raw[:budget] + "\n… [truncated]"
            budget -= len(raw.encode())
            lines.append(f"\n--- {fname} ---\n{raw}")
        except Exception:
            pass

    return ToolResult("\n".join(lines))


# ── registry ──────────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, AgentTool] = {
    "inspect_project": AgentTool(
        name="inspect_project",
        description=(
            "Inspect a project path. If it is a directory: detects project type, lists all files, "
            "and reads key metadata files (README, pyproject.toml, package.json, etc.) in one call. "
            "If it is a file: reads the file directly. "
            "Use this FIRST whenever the user mentions a project folder or an unknown path. "
            "Do NOT call read_file on a directory — always use inspect_project or list_dir instead."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to inspect (file or directory, relative or absolute)"},
            },
            "required": ["path"],
        },
        call=_inspect_project,
    ),
    "read_file": AgentTool(
        name="read_file",
        description=(
            "Read a file's contents with line numbers. "
            "Supports range reads via start_line/end_line for large files. "
            "Use this to get accurate file contents."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path":       {"type": "string",  "description": "File path relative to cwd or absolute"},
                "start_line": {"type": "integer", "description": "First line to read (1-indexed, default 1)",    "default": 1},
                "end_line":   {"type": "integer", "description": "Last line to read inclusive (0=all, default 0)", "default": 0},
            },
            "required": ["path"],
        },
        call=_read_file,
    ),
    "list_dir": AgentTool(
        name="list_dir",
        description="List a directory's contents with names, types, and sizes.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default '.')", "default": "."},
            },
        },
        call=_list_dir,
    ),
    "search_files": AgentTool(
        name="search_files",
        description=(
            "Search for a pattern across files in a directory tree. "
            "Returns matching lines with file path and line number."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern":   {"type": "string", "description": "Search pattern (regex or literal string)"},
                "path":      {"type": "string", "description": "Directory to search (default '.')",    "default": "."},
                "file_glob": {"type": "string", "description": "File name glob e.g. '*.py' (default '*')", "default": "*"},
            },
            "required": ["pattern"],
        },
        call=_search_files,
    ),
    "run_command": AgentTool(
        name="run_command",
        description=(
            "Run a shell command. Requires explicit user approval. "
            "Use only when file reading is insufficient."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string",  "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout seconds (default 30)", "default": 30},
            },
            "required": ["command"],
        },
        call=_run_command,
    ),
    "ask_user": AgentTool(
        name="ask_user",
        description="Ask the user a clarifying question when the request is ambiguous.",
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The clarifying question"},
            },
            "required": ["question"],
        },
        call=_ask_user,
    ),
}
