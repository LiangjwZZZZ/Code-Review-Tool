"""Integration tests for the review tool end-to-end pipeline."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from review.engine.diff_parser import get_diff, get_commit_info, parse_diff
from review.engine.report_generator import generate_report
from review.models import DiffChange, ImpactItem, Report, ReviewFinding
from review.store.report_store import DB_PATH as STORE_DB_PATH, save_report
from review.web.server import app


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repo with a sample commit."""
    repo = tmp_path / "test-repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, capture_output=True)

    (repo / "src").mkdir()
    (repo / "src" / "calculator.py").write_text(
        "def add(a, b):\n    return a + b\n\n"
        "def subtract(a, b):\n    return a - b\n"
    )
    (repo / "src" / "main.py").write_text(
        "from calculator import add\n\n"
        "def run():\n    return add(1, 2)\n"
    )
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True)

    (repo / "src" / "calculator.py").write_text(
        "def add(a, b, c=0):\n    return a + b + c\n\n"
        "def subtract(a, b):\n    return a - b\n\n"
        "def multiply(a, b):\n    return a * b\n"
    )
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: add multiply, extend add"], cwd=repo, capture_output=True)

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    yield str(repo), sha


@pytest.fixture
def report_data():
    """Sample Report instance for store/API tests."""
    return Report(
        commit_hash="int-abc123",
        commit_message="integration test commit",
        author="CI",
        risk_level="MEDIUM",
        changes=[DiffChange(file="src/lib.py", added=2, removed=1, hunks=["@@ -1,5 +1,6 @@"])],
        impacts=[ImpactItem(
            symbol="validate_input",
            symbol_kind="Function",
            file="src/lib.py",
            risk="HIGH",
            direction="upstream",
            affected_symbols=["process_data", "handle_request"],
            affected_processes=["Request -> validate_input -> process_data"],
            summary="Changes may affect 2 callers.",
        )],
        findings=[ReviewFinding(
            category="signature_change",
            severity="HIGH",
            message="validate_input signature changed",
            suggestion="Update callers in process_data.py",
        )],
        summary="1 medium issue",
    )


@pytest.fixture
def test_db_path(tmp_path):
    """Redirect store DB to temp path."""
    original = STORE_DB_PATH
    import review.store.report_store as rs
    rs.DB_PATH = tmp_path / "reports.db"
    yield rs.DB_PATH
    rs.DB_PATH = original


# ── Pipeline Tests ────────────────────────────────────────────────────────


class TestEndToEndPipeline:
    """Test the full pipeline: repo -> diff -> parse -> report (mocked impact/LLM)."""

    @staticmethod
    def _mock_impact(*args, **kwargs):
        return [ImpactItem(
            symbol="calculator.add",
            symbol_kind="Function",
            file="src/calculator.py",
            risk="HIGH",
            direction="upstream",
            affected_symbols=["main.run"],
            affected_processes=["run -> add"],
            summary="Signature change: add(a,b) -> add(a,b,c=0)",
        )]

    @staticmethod
    def _mock_llm(*args, **kwargs):
        return [ReviewFinding(
            category="signature_change",
            severity="HIGH",
            message="add() signature changed -- added optional parameter c=0",
            suggestion="Update callers to use new signature",
        )]

    @patch("review.engine.report_generator.analyze_changes")
    @patch("review.engine.report_generator.run_llm_review")
    def test_pipeline_generates_report(self, mock_llm, mock_impact, temp_repo):
        """End-to-end pipeline produces a valid Report."""
        repo_path, commit_hash = temp_repo
        mock_impact.side_effect = self._mock_impact
        mock_llm.side_effect = self._mock_llm

        report = generate_report(commit_hash, quick=False, repo_path=repo_path)

        assert report.commit_hash == commit_hash
        assert report.commit_message == "feat: add multiply, extend add"
        assert report.author == "Tester"
        assert report.risk_level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        assert len(report.changes) > 0
        assert any("calculator.py" in c.file for c in report.changes)
        assert len(report.impacts) > 0
        assert any("calculator" in i.symbol for i in report.impacts)
        assert len(report.findings) > 0
        assert len(report.summary) > 0
        assert report.created_at is not None

    @patch("review.engine.report_generator.analyze_changes")
    @patch("review.engine.report_generator.run_llm_review")
    def test_pipeline_serializable(self, mock_llm, mock_impact, temp_repo, test_db_path):
        """Report must be serializable to dict and storable in SQLite."""
        repo_path, commit_hash = temp_repo
        mock_impact.side_effect = self._mock_impact
        mock_llm.side_effect = self._mock_llm

        report = generate_report(commit_hash, quick=True, repo_path=repo_path)
        d = report.to_dict()
        json_str = json.dumps(d)
        assert len(json_str) > 0

        save_report(report)
        from review.store.report_store import load_report
        loaded = load_report(commit_hash)
        assert loaded is not None
        assert loaded.commit_hash == commit_hash
        assert len(loaded.changes) == len(report.changes)
        assert len(loaded.impacts) == len(report.impacts)
        assert len(loaded.findings) == len(report.findings)

    @patch("review.engine.report_generator.analyze_changes")
    @patch("review.engine.report_generator.run_llm_review")
    def test_pipeline_without_llm(self, mock_llm, mock_impact, temp_repo):
        """Pipeline degrades gracefully when LLM review returns empty findings."""
        repo_path, commit_hash = temp_repo
        mock_impact.side_effect = self._mock_impact
        mock_llm.return_value = []

        report = generate_report(commit_hash, quick=True, repo_path=repo_path)

        assert report.commit_hash == commit_hash
        assert len(report.findings) == 0
        assert len(report.impacts) > 0


class TestDiffAndParseRoundTrip:
    """Test git diff -> parse -> symbol extraction end-to-end."""

    def test_get_diff_and_parse(self, temp_repo):
        """Actual git diff output is correctly parsed."""
        repo_path, commit_hash = temp_repo
        diff_text = get_diff(commit_hash, repo_path)
        assert len(diff_text) > 0
        changes = parse_diff(diff_text)
        assert len(changes) > 0
        assert any("calculator.py" in c.file for c in changes)

    def test_commit_info(self, temp_repo):
        """Commit metadata is correctly extracted."""
        repo_path, commit_hash = temp_repo
        info = get_commit_info(commit_hash, repo_path)
        assert info["hash"] == commit_hash
        assert "multiply" in info["message"]

    def test_root_commit_diff(self, tmp_path):
        """Root commit (no parent) diff still works."""
        repo = tmp_path / "root-repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
        (repo / "readme.md").write_text("# Hello\n")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "root"], cwd=repo, capture_output=True)
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
        ).stdout.strip()
        diff = get_diff(sha, str(repo))
        assert "readme.md" in diff


class TestWebApiIntegration:
    """Test the web API with prepared report data."""

    def test_list_and_get_report(self, report_data, test_db_path):
        """API serves stored reports correctly."""
        save_report(report_data)
        client = TestClient(app)

        resp = client.get("/api/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert any(r["commit"] == "int-abc123" for r in data)

        resp = client.get("/api/reports/int-abc123")
        assert resp.status_code == 200
        body = resp.json()
        assert body["commit_hash"] == "int-abc123"
        assert len(body["changes"]) == 1
        assert body["changes"][0]["file"] == "src/lib.py"
        assert len(body["impacts"]) == 1
        assert body["impacts"][0]["symbol"] == "validate_input"
        assert len(body["findings"]) == 1

    def test_not_found(self):
        """404 for missing reports."""
        client = TestClient(app)
        resp = client.get("/api/reports/nonexistent")
        assert resp.status_code == 404

    def test_format_endpoint(self, report_data, test_db_path):
        """Report format endpoint returns markdown rendering."""
        save_report(report_data)
        client = TestClient(app)
        resp = client.get("/api/reports/int-abc123/format")
        assert resp.status_code == 200
        body = resp.json()
        assert "markdown" in body
        assert "validate_input" in body["markdown"]
        assert "HIGH" in body["markdown"]

    def test_multiple_reports_listing(self, report_data, test_db_path):
        """Multiple reports appear in listing."""
        save_report(report_data)
        r2 = Report(
            commit_hash="int-def456",
            commit_message="second report",
            author="CI",
            risk_level="LOW",
        )
        save_report(r2)
        client = TestClient(app)
        resp = client.get("/api/reports")
        data = resp.json()
        assert len(data) >= 2
        commit_hashes = [r["commit"] for r in data]
        assert "int-abc123" in commit_hashes
        assert "int-def456" in commit_hashes


class TestCliIntegration:
    """Test CLI commands run without errors (smoke tests)."""

    def test_cli_smoke(self):
        """All CLI top-level commands execute without crash."""
        from typer.testing import CliRunner
        from review.cli import app as cli_app

        runner = CliRunner()
        result = runner.invoke(cli_app, ["--help"])
        assert result.exit_code == 0
        assert "check" in result.output

        result = runner.invoke(cli_app, ["check", "--help"])
        assert result.exit_code == 0

        result = runner.invoke(cli_app, ["history", "--help"])
        assert result.exit_code == 0

    def test_cli_history_no_reports(self, test_db_path):
        """History command shows empty message when no reports."""
        from typer.testing import CliRunner
        from review.cli import app as cli_app

        runner = CliRunner()
        result = runner.invoke(cli_app, ["history"])
        assert result.exit_code == 0

    def test_cli_check_with_bad_commit(self):
        """Check command handles non-existent commit gracefully."""
        from typer.testing import CliRunner
        from review.cli import app as cli_app

        runner = CliRunner()
        result = runner.invoke(cli_app, ["check", "deadbeef0000000000000000", "--quick"])
        assert result.exit_code != 0 or "error" in result.output.lower()
