"""Gerrit change URL parsing and refspec generation."""

import re
import subprocess
from typing import Optional


def parse_gerrit_url(url: str) -> dict:
    """Parse a Gerrit change URL into its components.

    Supports:
      https://gerrit.example.com/c/project/+/12345/3
      https://gerrit.example.com/c/project/sub/+/12345
      https://gerrit.example.com/#/c/project/+/12345/3

    Returns dict with: host, project, change (int), patchset (int or None).
    Raises ValueError on invalid format.
    """
    # Normalize hash-based fragment URLs
    url = re.sub(r'/#/c/', '/c/', url)

    m = re.match(r'https?://([^/]+)', url)
    if not m:
        raise ValueError(f"Invalid Gerrit URL: no host found")
    host = m.group(1)

    # /c/<project>/+/<change>[/<patchset>]
    m = re.search(r'/c/(.+?)/\+/(\d+)(?:/(\d+))?', url)
    if not m:
        raise ValueError(
            f"Could not parse Gerrit change URL. "
            f"Expected: https://host/c/project/+/12345[/patchset]"
        )

    project = m.group(1).rstrip('/')
    change = int(m.group(2))
    patchset = int(m.group(3)) if m.group(3) else None

    return {"host": host, "project": project, "change": change, "patchset": patchset}


def get_refspec(change: int, patchset: Optional[int] = None) -> str:
    """Generate Gerrit refspec for git fetch.

    Gerrit stores changes at refs/changes/XX/YYYYYY/Z where:
      XX = last 2 digits of change number (zero-padded)
      YYYYYY = change number
      Z = patchset number

    When patchset is None, returns a wildcard to fetch the latest.
    """
    suffix = f"{change:02d}"[-2:]
    base = f"refs/changes/{suffix}/{change}"
    if patchset is not None:
        return f"{base}/{patchset}"
    return f"{base}/*"


def match_repo_to_gerrit(
    gerrit_host: str,
    gerrit_project: str,
    local_repo_paths: list[str],
    gerrit_repo_map: Optional[dict[str, str]] = None,
) -> Optional[str]:
    """Find the local repo that matches a Gerrit host + project.

    Priority:
      1. Explicit gerrit_repo_map (Gerrit project → local path)
      2. Auto-detect by checking each repo's git remote URL
    """
    if gerrit_repo_map and gerrit_project in gerrit_repo_map:
        return gerrit_repo_map[gerrit_project]

    for repo_path in local_repo_paths:
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, cwd=repo_path,
                timeout=10,
            )
            if result.returncode != 0:
                continue
            remote_url = result.stdout.strip()
            if gerrit_host in remote_url and gerrit_project in remote_url:
                return repo_path
        except (subprocess.TimeoutExpired, OSError):
            continue

    return None
