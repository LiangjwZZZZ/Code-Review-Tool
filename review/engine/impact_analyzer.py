import json
import subprocess
import re
import sys
from pathlib import Path
from typing import Optional

from review.models import ImpactItem


SUBPROCESS_TIMEOUT = 30
GITNEXUS_INDEX_DIR = Path.home() / ".review" / "gitnexus"


def find_gitnexus_command() -> Optional[str]:
    """Find gitnexus command based on platform.

    Discovery order:
    1. Windows: check for bundled gitnexus.exe in tool directory
    2. All platforms: try npx gitnexus (downloads to temp)
    3. Fallback: check PATH for gitnexus
    """
    # 1. Windows bundled exe
    if sys.platform == "win32":
        exe_path = Path(sys.executable).parent / "gitnexus.exe"
        if exe_path.exists():
            return str(exe_path)

    # 2. Try npx (works on all platforms with Node.js)
    try:
        result = subprocess.run(
            ["npx", "gitnexus", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return "npx"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 3. Check PATH
    try:
        result = subprocess.run(
            ["gitnexus", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return "gitnexus"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def _build_gitnexus_cmd(base_cmd: str, args: list[str], repo_path: str) -> list[str]:
    """Build full gitnexus command with proper arguments."""
    if base_cmd == "npx":
        return ["npx", "gitnexus"] + args + ["--repo", repo_path]
    else:
        return [base_cmd] + args + ["--repo", repo_path]


def ensure_index(repo_path: str, force: bool = False) -> bool:
    """Ensure gitnexus index exists for the repo.

    Returns True if index is ready, False if indexing failed.
    """
    cmd = find_gitnexus_command()
    if not cmd:
        return False

    repo_name = Path(repo_path).resolve().name
    index_dir = GITNEXUS_INDEX_DIR / repo_name

    # Check if index exists and is fresh
    if not force and index_dir.exists():
        # Index exists, assume it's valid
        return True

    # Run gitnexus analyze
    analyze_cmd = _build_gitnexus_cmd(cmd, ["analyze"], repo_path)
    try:
        result = subprocess.run(
            analyze_cmd,
            capture_output=True, text=True,
            timeout=300,  # 5 minutes for initial indexing
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def analyze_symbol(
    symbol: str,
    file_path: Optional[str] = None,
    repo_path: str = ".",
) -> Optional[ImpactItem]:
    """Run gitnexus impact on a single symbol and return ImpactItem.

    Returns None if the symbol isn't indexed or gitnexus fails.
    """
    cmd = find_gitnexus_command()
    if not cmd:
        return None

    args = ["impact", symbol, "--direction", "upstream"]
    if file_path:
        args.extend(["--file-path", file_path])

    full_cmd = _build_gitnexus_cmd(cmd, args, repo_path)

    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT
        )
        if result.returncode != 0:
            return None

        output = result.stdout
        return _parse_gitnexus_output(symbol, output, file_path or "")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _parse_gitnexus_output(symbol: str, output: str, file_path: str) -> ImpactItem:
    """Parse gitnexus impact CLI output into ImpactItem."""
    affected = []
    processes = []
    risk = "MEDIUM"

    # Extract risk level
    risk_match = re.search(r"risk:\s*(CRITICAL|HIGH|MEDIUM|LOW)", output, re.IGNORECASE)
    risk = _parse_risk(risk_match.group(1)) if risk_match else "MEDIUM"

    # Extract affected symbols
    for line in output.split("\n"):
        line = line.strip()
        if re.match(r"^[a-zA-Z0-9_/.-]+\.[a-zA-Z]+:\d+", line):
            affected.append(line.split()[0])
        elif re.match(r"^\s*[•\-]", line):
            affected.append(line.lstrip("•- ").strip())
        if "process" in line.lower() or "execution" in line.lower():
            processes.append(line.strip())

    # Determine kind from symbol naming convention
    kind = "Function"
    if symbol[0].isupper():
        kind = "Class"
    if symbol.startswith("test_"):
        kind = "Test"

    return ImpactItem(
        symbol=symbol,
        symbol_kind=kind,
        file=file_path,
        risk=risk,
        direction="upstream",
        affected_symbols=affected[:20],
        affected_processes=processes[:5],
        summary=output[:500],
    )


def _parse_risk(risk_str: str) -> str:
    """Normalize risk string."""
    risk_str = risk_str.upper().strip()
    for valid in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if valid in risk_str:
            return valid
    return "MEDIUM"


def analyze_changes(symbols: list[str], file_map: dict[str, str], repo_path: str = ".") -> list[ImpactItem]:
    """Analyze multiple changed symbols via gitnexus."""
    impacts = []
    for sym in symbols:
        file_path = file_map.get(sym, "")
        item = analyze_symbol(sym, file_path, repo_path)
        if item:
            impacts.append(item)
    return impacts
