from review.models import Report, ReviewFinding, DiffChange, ImpactItem
from review.engine.llm_reviewer import (
    build_review_prompt,
    _fallback_findings,
    _parse_findings,
)


def test_build_review_prompt_includes_changes():
    report = Report(
        commit_hash="abc", commit_message="fix: update auth", author="dev",
        risk_level="HIGH",
        changes=[DiffChange(file="src/auth.py", added=3, removed=1, hunks=["@@ -1 +1,3 @@"])],
        impacts=[ImpactItem(symbol="validate", symbol_kind="Function", file="src/auth.py", risk="HIGH", direction="upstream")],
    )
    prompt = build_review_prompt(report.commit_message, report.changes, report.impacts)
    assert "src/auth.py" in prompt
    assert "validate" in prompt


def test_fallback_findings_high_risk():
    report = Report(
        commit_hash="abc", commit_message="fix", author="dev", risk_level="HIGH",
        impacts=[ImpactItem(symbol="validate", symbol_kind="Function", file="auth.py", risk="HIGH", direction="upstream", affected_symbols=["caller1"])],
    )
    findings = _fallback_findings(report)
    # First finding is the analysis summary, second is the breaking_change
    assert len(findings) == 2
    assert findings[0].category == "analysis"
    assert findings[1].severity == "HIGH"


def test_fallback_findings_low_risk():
    report = Report(
        commit_hash="abc", commit_message="fix", author="dev", risk_level="LOW",
    )
    findings = _fallback_findings(report)
    assert len(findings) == 1
    assert findings[0].category == "analysis"


def test_parse_findings_json():
    content = '[{"category": "breaking_change", "severity": "HIGH", "message": "Invalid", "suggestion": "Fix it"}]'
    findings = _parse_findings(content)
    assert len(findings) == 1
    assert findings[0].category == "breaking_change"
    assert findings[0].severity == "HIGH"
