"""Gerrit change URL parsing and refspec generation."""

import re
import subprocess
import urllib.request
import ssl
import json
from typing import Optional
from review.utils import hide_window
from review.config import load_config


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


def get_latest_patchset(
    host: str,
    change: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Optional[int]:
    """Query Gerrit REST API to get the latest patchset number for a change.

    Uses the authenticated endpoint (/a/changes/) when credentials are provided.
    Returns the patchset number, or None if the API is unreachable.
    """
    # Strip whitespace from credentials
    if username:
        username = username.strip()
    if password:
        password = password.strip()

    # Use authenticated endpoint when credentials are supplied
    if username and password:
        api_url = f"https://{host}/a/changes/{change}?o=CURRENT_REVISION"
    else:
        api_url = f"https://{host}/changes/{change}?o=CURRENT_REVISION"

    try:
        req = urllib.request.Request(api_url)
        if username and password:
            import base64
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            req.add_header("Authorization", f"Basic {token}")

        # Create SSL context that skips verification for internal Gerrit servers
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Bypass system proxy for internal Gerrit servers
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ctx)
        )
        with opener.open(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        # Strip Gerrit's anti-XSSI prefix
        raw = re.sub(r"^\)\]\}'\s*", "", raw)
        data = json.loads(raw)
        revisions = data.get("revisions", {})
        if not revisions:
            return None
        return max(v["_number"] for v in revisions.values())
    except Exception as e:
        print(f"Gerrit API error: {e}")
        return None


def get_refspec(change: int, patchset: int) -> str:
    """Generate Gerrit refspec for git fetch.

    Gerrit stores changes at refs/changes/XX/YYYYYY/Z where:
      XX = last 2 digits of change number (zero-padded)
      YYYYYY = change number
      Z = patchset number
    """
    suffix = f"{change:02d}"[-2:]
    return f"refs/changes/{suffix}/{change}/{patchset}"


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

    cfg = load_config()
    git_cmd = cfg.get("git_path") or "git"

    for repo_path in local_repo_paths:
        try:
            result = subprocess.run(
                [git_cmd, "remote", "get-url", "origin"],
                capture_output=True, text=True, encoding="utf-8", cwd=repo_path,
                timeout=10, **hide_window(),
            )
            if result.returncode != 0:
                continue
            remote_url = result.stdout.strip()
            if gerrit_host in remote_url and gerrit_project in remote_url:
                return repo_path
        except (subprocess.TimeoutExpired, OSError):
            continue

    return None
