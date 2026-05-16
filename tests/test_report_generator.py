from review.models import ImpactItem, ReviewFinding
from review.engine.report_generator import _determine_overall_risk, _build_summary


def test_determine_risk_critical():
    impacts = [ImpactItem(symbol="x", symbol_kind="F", file="x.py", risk="CRITICAL", direction="upstream")]
    assert _determine_overall_risk(impacts, []) == "CRITICAL"


def test_determine_risk_high():
    impacts = [ImpactItem(symbol="x", symbol_kind="F", file="x.py", risk="HIGH", direction="upstream")]
    assert _determine_overall_risk(impacts, []) == "HIGH"


def test_determine_risk_medium():
    impacts = [ImpactItem(symbol="x", symbol_kind="F", file="x.py", risk="LOW", direction="upstream")]
    assert _determine_overall_risk(impacts, []) == "MEDIUM"


def test_determine_risk_low():
    assert _determine_overall_risk([], []) == "LOW"


def test_build_summary_empty():
    from review.models import Report
    r = Report(commit_hash="a", commit_message="m", author="dev", risk_level="LOW")
    assert "No significant" in _build_summary(r)
