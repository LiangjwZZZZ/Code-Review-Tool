import re
import subprocess
from pathlib import Path
from review.models import DiffChange
from review.utils import hide_window
from review.config import load_config

SUBPROCESS_TIMEOUT = 30
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf899d153036e1a5c"


def _get_git_command() -> str:
    """Get the git command to use, from config or system default."""
    cfg = load_config()
    return cfg.get("git_path") or "git"


def get_commit_info(commit_hash: str, repo_path: str = ".") -> dict:
    """Get commit metadata (hash, message, body, author, time)."""
    git_cmd = _get_git_command()
    result = subprocess.run(
        [git_cmd, "log", "-1", "--format=%H%x00%s%x00%b%x00%an%x00%ai", commit_hash],
        capture_output=True, text=True, encoding="utf-8", cwd=repo_path, timeout=SUBPROCESS_TIMEOUT,
        **hide_window(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")
    stdout = result.stdout or ""
    parts = stdout.strip().split("\0")
    return {
        "hash": parts[0] if len(parts) > 0 else "",
        "message": parts[1] if len(parts) > 1 else "",
        "body": parts[2].strip() if len(parts) > 2 else "",
        "author": parts[3] if len(parts) > 3 else "",
        "time": parts[4] if len(parts) > 4 else "",
    }


def get_diff(commit_hash: str, repo_path: str = ".") -> str:
    """Get diff for a commit. Handles root commits (no parent) correctly."""
    git_cmd = _get_git_command()
    result = subprocess.run(
        [git_cmd, "diff-tree", "--no-commit-id", "-r", "-p", "--root", commit_hash, "--"],
        capture_output=True, text=True, encoding="utf-8", cwd=repo_path, timeout=SUBPROCESS_TIMEOUT,
        **hide_window(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"git diff-tree failed: {result.stderr}")
    return result.stdout or ""


def parse_diff(diff_text: str) -> list[DiffChange]:
    """Parse unified diff output into structured changes."""
    changes = []
    current_file = None
    added = removed = 0
    hunks = []

    for line in diff_text.split("\n"):
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("diff --git "):
            if current_file:
                changes.append(DiffChange(file=current_file, added=added, removed=removed, hunks=hunks))
            # Extract the b/ path from "diff --git a/path b/path"
            parts = line.split()
            current_file = parts[-1][2:] if len(parts) >= 4 else parts[-1]
            added = removed = 0
            hunks = []
        elif line.startswith("@@"):
            hunks.append(line)
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1

    if current_file:
        changes.append(DiffChange(file=current_file, added=added, removed=removed, hunks=hunks))
    return changes


def get_changed_symbols(changes: list[DiffChange], diff_text: str = "") -> list[str]:
    """Extract symbol-like names from changed files.

    For Java files, extracts actual method/class names from the diff.
    For other files, falls back to filename stem.
    """
    symbols = []
    file_diffs = _split_diff_by_file(diff_text) if diff_text else {}

    for c in changes:
        if c.file.endswith(".java"):
            java_symbols = _extract_java_symbols(c.file, file_diffs.get(c.file, ""))
            symbols.extend(java_symbols)
        else:
            stem = Path(c.file).stem
            symbols.append(stem)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


_JAVA_CLASS_PATTERN = re.compile(
    r'(?:public|protected|private)?\s*(?:abstract|final|static)?\s*class\s+(\w+)'
)
_JAVA_METHOD_PATTERN = re.compile(
    r'(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?[\w<>\[\]]+\s+(\w+)\s*\('
)


def _split_diff_by_file(diff_text: str) -> dict[str, str]:
    """Split full diff by file, return {file_path: diff_section}."""
    files: dict[str, list[str]] = {}
    current_file = None

    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            if current_file is not None:
                files[current_file] = files.get(current_file, [])
            parts = line.split()
            current_file = parts[-1][2:] if len(parts) >= 4 else parts[-1]
            files.setdefault(current_file, []).append(line)
        elif current_file is not None:
            files[current_file].append(line)

    return {k: "\n".join(v) for k, v in files.items()}


def _extract_java_symbols(file_path: str, diff_section: str) -> list[str]:
    """Extract Java symbols modified in the diff.

    Tries to read the actual file to determine symbol ranges.
    Falls back to extracting from diff text directly.
    """
    if not diff_section:
        return []

    # Find modified line numbers from diff
    modified_lines = _collect_modified_lines(diff_section)

    if modified_lines:
        # Try to read the actual file for precise symbol mapping
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                file_lines = f.readlines()
            symbol_ranges = _build_symbol_ranges(file_lines)
            symbols = [
                symbol
                for symbol, (start, end) in symbol_ranges.items()
                if any(start <= line <= end for line in modified_lines)
            ]
            if symbols:
                return symbols
        except (OSError, IOError):
            pass

    # Fallback: extract symbols from added lines in the diff
    return _extract_symbols_from_diff_text(diff_section)


def _collect_modified_lines(diff_section: str) -> set[int]:
    """Parse hunk headers and diff lines to collect 0-based modified line numbers."""
    modified_lines: set[int] = set()
    current_line = 0

    for line in diff_section.split("\n"):
        if line.startswith("@@"):
            match = re.search(r'\+(\d+)', line)
            if match:
                current_line = int(match.group(1)) - 1
        elif line.startswith("+") and not line.startswith("+++"):
            modified_lines.add(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass  # removed lines don't increment the new-file counter
        else:
            current_line += 1

    return modified_lines


def _extract_symbols_from_diff_text(diff_text: str) -> list[str]:
    """Fallback: extract symbols directly from added lines in the diff."""
    symbols = []
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            code = line[1:].strip()
            match = _JAVA_METHOD_PATTERN.search(code)
            if match:
                symbols.append(match.group(1))
            match = _JAVA_CLASS_PATTERN.search(code)
            if match:
                symbols.append(match.group(1))
    return symbols


def _build_symbol_ranges(file_lines: list[str]) -> dict[str, tuple[int, int]]:
    """Build mapping of symbol name -> (start_line, end_line) from file content."""
    ranges: dict[str, tuple[int, int]] = {}
    symbol_stack: list[tuple[str, int, int]] = []  # (name, start, brace_depth)
    brace_depth = 0

    for i, line in enumerate(file_lines):
        stripped = line.strip()

        # Check for method or class declaration
        method_match = _JAVA_METHOD_PATTERN.search(stripped)
        class_match = _JAVA_CLASS_PATTERN.search(stripped)

        if method_match or class_match:
            name = (method_match or class_match).group(1)
            symbol_stack.append((name, i, brace_depth))

        # Count braces at this depth level
        for ch in stripped:
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                # Check if any symbol's body ends here
                while symbol_stack and symbol_stack[-1][2] >= brace_depth:
                    name, start, _ = symbol_stack.pop()
                    ranges[name] = (start, i)

    return ranges
