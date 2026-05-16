from typer.testing import CliRunner
from review.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Analyze a commit's impact" in result.stdout


def test_cli_check_missing_commit():
    result = runner.invoke(app, ["check"])
    assert result.exit_code != 0


def test_cli_history_empty():
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0


def test_cli_index_help():
    result = runner.invoke(app, ["index", "--help"])
    assert result.exit_code == 0
