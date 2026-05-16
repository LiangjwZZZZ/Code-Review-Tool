from review.models import Report, DiffChange, ImpactItem, ReviewFinding
from review.engine.diff_parser import get_commit_info, get_diff, parse_diff, get_changed_symbols
from review.engine.impact_analyzer import analyze_changes
from review.engine.llm_reviewer import run_llm_review


def _determine_overall_risk(impacts: list[ImpactItem], findings: list[ReviewFinding]) -> str:
    for item in impacts:
        if item.risk == "CRITICAL":
            return "CRITICAL"
        if item.risk == "HIGH":
            return "HIGH"
    if impacts:
        return "MEDIUM"
    return "LOW"


def generate_report(commit_hash: str, quick: bool = False, repo_path: str = ".") -> Report:
    """Generate a full review report for a given commit."""
    info = get_commit_info(commit_hash, repo_path)
    diff_text = get_diff(commit_hash, repo_path)
    changes = parse_diff(diff_text)
    symbols = get_changed_symbols(changes)

    file_map = {s: c.file for c in changes for s in get_changed_symbols([c])}
    impacts = analyze_changes(symbols, file_map, repo_path)

    from pathlib import Path
    repo_name = Path(repo_path).resolve().name

    report = Report(
        commit_hash=info["hash"],
        commit_message=info["message"],
        commit_body=info.get("body", ""),
        commit_time=info.get("time", ""),
        repo_name=repo_name,
        author=info["author"],
        risk_level="MEDIUM",
        changes=changes,
        impacts=impacts,
    )

    if not quick:
        findings = run_llm_review(report, diff_text=diff_text)
        report.findings = findings

    report.risk_level = _determine_overall_risk(report.impacts, report.findings)
    report.summary = _build_summary(report)
    return report


def _build_summary(report: Report) -> str:
    parts = []
    breaking = [f for f in report.findings if f.severity in ("CRITICAL", "HIGH")]
    if breaking:
        parts.append(f"{len(breaking)} high-severity issue(s)")
    high_impacts = [i for i in report.impacts if i.risk in ("CRITICAL", "HIGH")]
    if high_impacts:
        parts.append(f"{len(high_impacts)} high-risk impact(s)")
    if not parts:
        parts.append("No significant issues detected")
    return ", ".join(parts)
