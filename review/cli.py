import sys
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from review.engine.report_generator import generate_report
from review.store.report_store import save_report, load_report, list_reports

app = typer.Typer(name="review")


@app.callback()
def callback():
    """review — Analyze a commit's impact on existing code using GitNexus + Graphify."""


@app.command()
def check(
    commit: str = typer.Argument(..., help="Commit hash to review"),
    quick: bool = typer.Option(False, "--quick", help="Skip LLM review, only impact analysis"),
    deep: bool = typer.Option(False, "--deep", help="Also build Graphify code tree visualization"),
    repo: str = typer.Option(".", "--repo", help="Repository path"),
):
    """Review a specific commit."""
    typer.echo(f"\n  Analyzing commit {commit}...\n")

    report = generate_report(commit, quick=quick, repo_path=repo)
    save_report(report)

    _print_summary(report)

    if deep:
        typer.echo("\n  Building Graphify code tree...")
        _run_graphify(repo)

    _print_urls("127.0.0.1", 9090, f"/report/{commit}")
    typer.echo(f"  Run: review web {commit}")


@app.command()
def diff(
    branch: str = typer.Argument(..., help="Branch name"),
    base: str = typer.Argument("main", help="Base branch"),
):
    """Review changes between two branches."""
    typer.echo(f"  Diff review: {branch} vs {base} (NYI)")
    typer.echo("  Use 'review check' with a merge-base commit for now.")


@app.command()
def status(
    quick: bool = typer.Option(False, "--quick"),
):
    """Review uncommitted changes in working tree."""
    typer.echo("  Status review (NYI)")
    typer.echo("  Stage your changes and use 'review check' on the staged commit.")


@app.command()
def web(
    commit: Optional[str] = typer.Argument(None, help="Commit hash to view"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (use 0.0.0.0 for LAN access)"),
    port: int = typer.Option(9090, "--port", "-p", help="Web server port"),
):
    """Start web UI to view review reports."""
    from review.web.server import start_server

    if commit:
        report = load_report(commit)
        if not report:
            typer.echo(f"  No report found for commit {commit}", err=True)
            raise typer.Exit(1)
        typer.echo(f"  Opening report for {commit}...")

    _print_urls(host, port)
    webbrowser.open(f"http://localhost:{port}")
    start_server(host=host, port=port)


@app.command()
def index(
    repo: str = typer.Option(".", "--repo", help="Repository path"),
):
    """Initialize/update GitNexus index for the repository."""
    import subprocess
    typer.echo(f"  Indexing repository at {repo}...")
    result = subprocess.run(
        ["gitnexus", "analyze", repo],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        typer.echo("  Index complete.")
    else:
        typer.echo(f"  Index failed: {result.stderr}", err=True)
        raise typer.Exit(1)


@app.command()
def history():
    """List recent review reports."""
    reports = list_reports()
    if not reports:
        typer.echo("  No reports found.")
        return
    typer.echo("\n  Recent reviews:")
    for r in reports:
        msg = r.get("commit_message", "")
        typer.echo(f"  {r['commit'][:12]}  {r.get('commit_time', '')[:10]}  {r['author']}  [{r['risk_level']}]  {msg[:60]}")


def _lan_ip() -> str:
    """Get LAN IP address."""
    import subprocess
    for iface in ("en0", "en1"):
        try:
            r = subprocess.run(["ipconfig", "getifaddr", iface], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    return ""


def _print_urls(host: str, port: int, path: str = ""):
    """Print accessible URLs for the web server."""
    typer.echo(f"  Local:   http://localhost:{port}{path}")
    if host == "0.0.0.0":
        ip = _lan_ip()
        if ip:
            typer.echo(f"  Network: http://{ip}:{port}{path}")
        else:
            typer.echo("  Network: (connect to your LAN IP on port {port})")


def _print_summary(report):
    """Print terminal summary of review report."""
    typer.echo(f"  commit {report.commit_hash[:12]} - {report.commit_message}")
    typer.echo(f"  author: {report.author}  |  files: {len(report.changes)}  |  ++ {sum(c.added for c in report.changes)}  -- {sum(c.removed for c in report.changes)}")
    typer.echo("")
    typer.echo(f"  RISK: {report.risk_level}")

    if report.findings:
        typer.echo(f"\n  \U0001f50d LLM Analysis ({len(report.findings)} findings):")
        sev_icons = {"CRITICAL": "\U0001f534", "HIGH": "\U0001f7e1", "MEDIUM": "\U0001f7e0", "LOW": "\U0001f7e2", "INFO": "ℹ️"}
        for f in report.findings:
            icon = sev_icons.get(f.severity, "ℹ️")
            typer.echo(f"    {icon} [{f.severity}] {f.category}")
            typer.echo(f"       {f.message}")
            if f.suggestion:
                typer.echo(f"       \U0001f4a1 {f.suggestion}")

    high_impacts = [i for i in report.impacts if i.risk in ("CRITICAL", "HIGH")]
    if high_impacts:
        typer.echo(f"\n  \U0001f7e1 High risk impacts ({len(high_impacts)}):")
        for i in high_impacts[:3]:
            typer.echo(f"    • {i.symbol} ({i.file})")

    modules = set()
    for c in report.changes:
        parts = Path(c.file).parts
        if len(parts) > 1:
            modules.add(parts[0])
    if modules:
        typer.echo(f"\n  Modules affected: {', '.join(sorted(modules))}")

    typer.echo(f"\n  {report.summary}")


def _run_graphify(repo_path: str):
    """Build Graphify code tree and generate HTML visualization."""
    import subprocess
    import time
    from pathlib import Path
    import typer

    graphify_out = Path(repo_path) / "graphify-out"

    typer.echo("    Updating code graph...")
    result = subprocess.run(
        ["graphify", "update", repo_path],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        typer.echo(f"    Graph update failed: {result.stderr.strip() or 'see graphify output'}")
        return

    tree_html = graphify_out / "GRAPH_TREE.html"
    typer.echo("    Generating tree visualization...")
    subprocess.run(
        ["graphify", "tree", "--graph", str(graphify_out / "graph.json"),
         "--output", str(tree_html), "--label", Path(repo_path).name],
        capture_output=True, text=True, timeout=60,
    )

    if tree_html.exists():
        typer.echo(f"    Code tree: file://{tree_html}")
    else:
        typer.echo("    Tree visualization not generated (try: graphify extract --no-cluster)")
