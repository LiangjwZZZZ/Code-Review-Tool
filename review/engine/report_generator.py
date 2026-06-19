from review.models import Report, DiffChange, ImpactItem, ReviewFinding, FileAnalysis
from review.engine.diff_parser import get_commit_info, get_diff, parse_diff, get_changed_symbols
from review.engine.impact_analyzer import analyze_changes
from review.engine.llm_reviewer import run_llm_review
from review.engine.module_detector import detect_modules, file_to_module


def _determine_overall_risk(impacts: list[ImpactItem], findings: list[ReviewFinding]) -> str:
    for item in impacts:
        if item.risk == "CRITICAL":
            return "CRITICAL"
        if item.risk == "HIGH":
            return "HIGH"
    if impacts:
        return "MEDIUM"
    return "LOW"


def _get_per_file_diffs(diff_text: str) -> dict[str, str]:
    """Split full diff by file, return {file_path: diff_section}."""
    files = {}
    current_file = None
    current_lines = []

    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            if current_file and current_lines:
                files[current_file] = "\n".join(current_lines)
            parts = line.split()
            # Extract path from "diff --git a/path b/path"
            current_file = parts[-1][2:] if len(parts) >= 4 else parts[-1]
            current_lines = [line]
        elif current_file is not None:
            current_lines.append(line)

    if current_file and current_lines:
        files[current_file] = "\n".join(current_lines)
    return files


def _filter_impacts_for_file(impacts: list[ImpactItem], file_path: str) -> list[ImpactItem]:
    """Keep only ImpactItems whose symbol definition or affected files involve the given file."""
    filtered = []
    for imp in impacts:
        if imp.file == file_path:
            filtered.append(imp)
            continue
        if file_path in imp.affected_symbols:
            filtered.append(imp)
            continue
    return filtered


def _build_cross_module_impacts(
    changes: list[DiffChange],
    impacts: list[ImpactItem],
    modules: list[dict],
) -> list[dict]:
    """Calculate cross-module impact chains from the impact analysis."""
    cross = {}
    for imp in impacts:
        src_module = file_to_module(imp.file, modules)
        for affected in imp.affected_symbols[:20]:
            dst_module = file_to_module(affected, modules)
            if src_module and dst_module and src_module != dst_module:
                key = f"{src_module}→{dst_module}"
                if key not in cross:
                    cross[key] = {
                        "from_module": src_module,
                        "to_module": dst_module,
                        "symbols": [],
                        "risk": imp.risk,
                    }
                if imp.symbol not in cross[key]["symbols"]:
                    cross[key]["symbols"].append(imp.symbol)
                if _risk_score(imp.risk) > _risk_score(cross[key]["risk"]):
                    cross[key]["risk"] = imp.risk
    return list(cross.values())


def _risk_score(risk: str) -> int:
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(risk, 0)


def generate_report(commit_hash: str, quick: bool = False, repo_path: str = ".") -> Report:
    """Generate a full review report for a given commit."""
    info = get_commit_info(commit_hash, repo_path)

    modules = detect_modules(repo_path)

    diff_text = get_diff(commit_hash, repo_path)
    changes = parse_diff(diff_text)
    symbols = get_changed_symbols(changes, diff_text)

    file_map = {s: c.file for c in changes for s in get_changed_symbols([c], diff_text)}
    impacts = analyze_changes(symbols, file_map, repo_path)

    from pathlib import Path
    repo_name = Path(repo_path).resolve().name

    # Build per-file analyses
    per_file_diffs = _get_per_file_diffs(diff_text)
    file_analyses = []
    for c in changes:
        fa = FileAnalysis(
            file=c.file,
            diff_text=per_file_diffs.get(c.file, ""),
            impacts=_filter_impacts_for_file(impacts, c.file),
            module=file_to_module(c.file, modules),
        )
        file_analyses.append(fa)

    # Build cross-module impacts
    cross_module_impacts = _build_cross_module_impacts(changes, impacts, modules)

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
        file_analyses=file_analyses,
        cross_module_impacts=cross_module_impacts,
        modules=modules,
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
