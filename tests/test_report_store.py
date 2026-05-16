from review.models import Report, DiffChange, ImpactItem, ReviewFinding
from review.store.report_store import save_report, load_report, list_reports


def test_save_and_load_report(tmp_path):
    import review.store.report_store as rs
    rs.DB_PATH = tmp_path / "reports.db"

    report = Report(
        commit_hash="abc123",
        commit_message="fix: resolve null pointer",
        author="dev",
        risk_level="HIGH",
        changes=[DiffChange(file="src/main.py", added=5, removed=2, hunks=["@@ -1,5 +1,8 @@"])],
        impacts=[ImpactItem(symbol="validate", symbol_kind="Function", file="src/main.py", risk="HIGH", direction="upstream")],
        findings=[ReviewFinding(category="breaking_change", severity="HIGH", message="Signature changed", suggestion="Update callers")],
        summary="3 issues found",
    )

    save_report(report)
    loaded = load_report("abc123")
    assert loaded is not None
    assert loaded.commit_hash == "abc123"
    assert loaded.risk_level == "HIGH"
    assert len(loaded.findings) == 1
    assert isinstance(loaded.findings[0], ReviewFinding)
    assert loaded.findings[0].suggestion == "Update callers"
    assert isinstance(loaded.changes[0], DiffChange)
    assert loaded.changes[0].file == "src/main.py"
    assert isinstance(loaded.impacts[0], ImpactItem)
    assert loaded.impacts[0].symbol == "validate"

    lst = list_reports()
    assert len(lst) == 1
    assert lst[0]["commit"] == "abc123"
