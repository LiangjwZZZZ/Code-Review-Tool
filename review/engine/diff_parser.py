import subprocess
from pathlib import Path
from review.models import DiffChange
from review.utils import hide_window

SUBPROCESS_TIMEOUT = 30
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf899d153036e1a5c"


def get_commit_info(commit_hash: str, repo_path: str = ".") -> dict:
    """Get commit metadata (hash, message, body, author, time)."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H%x00%s%x00%b%x00%an%x00%ai", commit_hash],
        capture_output=True, text=True, cwd=repo_path, timeout=SUBPROCESS_TIMEOUT,
        **hide_window(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")
    parts = result.stdout.strip().split("\0")
    return {
        "hash": parts[0] if len(parts) > 0 else "",
        "message": parts[1] if len(parts) > 1 else "",
        "body": parts[2].strip() if len(parts) > 2 else "",
        "author": parts[3] if len(parts) > 3 else "",
        "time": parts[4] if len(parts) > 4 else "",
    }


def get_diff(commit_hash: str, repo_path: str = ".") -> str:
    """Get diff for a commit. Handles root commits (no parent) correctly."""
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "-r", "-p", "--root", commit_hash, "--"],
        capture_output=True, text=True, cwd=repo_path, timeout=SUBPROCESS_TIMEOUT,
        **hide_window(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"git diff-tree failed: {result.stderr}")
    return result.stdout


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


def get_changed_symbols(changes: list[DiffChange]) -> list[str]:
    """Extract symbol-like names from changed file paths (filename stems)."""
    symbols = []
    for c in changes:
        stem = Path(c.file).stem
        symbols.append(stem)
    return symbols
