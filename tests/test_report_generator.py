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


def test_generate_report_uses_java_symbols():
    """Test that generate_report extracts Java symbols correctly."""
    from review.engine.report_generator import generate_report
    from unittest.mock import patch, MagicMock

    mock_info = {"hash": "abc123", "message": "test commit", "author": "test", "time": "2026-01-01"}
    mock_diff = """diff --git a/src/Foo.java b/src/Foo.java
+    public void newMethod() {
"""
    mock_changes = [MagicMock(file="src/Foo.java", added=1, removed=0)]

    with patch('review.engine.report_generator.get_commit_info', return_value=mock_info), \
         patch('review.engine.report_generator.get_diff', return_value=mock_diff), \
         patch('review.engine.report_generator.parse_diff', return_value=mock_changes), \
         patch('review.engine.report_generator.get_changed_symbols', return_value=["newMethod"]) as mock_symbols, \
         patch('review.engine.report_generator.analyze_changes', return_value=[]), \
         patch('review.engine.report_generator.run_llm_review', return_value=[]):
        report = generate_report("abc123", quick=True)
        # Verify get_changed_symbols was called with diff_text
        mock_symbols.assert_called_with(mock_changes, mock_diff)
