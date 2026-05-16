import json
import subprocess
import re
from typing import Optional
from review.models import ImpactItem


SUBPROCESS_TIMEOUT = 30


def _parse_risk(risk_str: str) -> str:
    """Normalize risk string."""
    risk_str = risk_str.upper().strip()
    for valid in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if valid in risk_str:
            return valid
    return "MEDIUM"


def analyze_symbol(
    symbol: str,
    file_path: Optional[str] = None,
    repo_path: str = ".",
) -> Optional[ImpactItem]:
    """Run gitnexus impact on a single symbol and return ImpactItem.

    Returns None if the symbol isn't indexed or gitnexus fails.
    """
    cmd = ["gitnexus", "impact", symbol, "--direction", "upstream", "--repo", repo_path]
    if file_path:
        cmd.extend(["--file-path", file_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT)
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


def analyze_changes(symbols: list[str], file_map: dict[str, str], repo_path: str = ".") -> list[ImpactItem]:
    """Analyze multiple changed symbols via gitnexus."""
    impacts = []
    for sym in symbols:
        file_path = file_map.get(sym, "")
        item = analyze_symbol(sym, file_path, repo_path)
        if item:
            impacts.append(item)
    return impacts
