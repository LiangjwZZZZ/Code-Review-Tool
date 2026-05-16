import datetime
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from review.config import load_config, save_config, get_env_from_config, get_log_dir
from review.store.report_store import load_report, list_reports


def _log_event(event: str):
    """Write a log event to the configured log directory."""
    cfg = load_config()
    log_dir = get_log_dir(cfg)
    log_file = log_dir / f"server-{datetime.datetime.now():%Y-%m-%d}.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {event}\n")
    except OSError:
        pass

app = FastAPI(title="Review Tool API")


@app.get("/api/reports")
def api_list_reports():
    return JSONResponse(list_reports())


@app.get("/api/reports/{commit_hash}")
def api_get_report(commit_hash: str):
    report = load_report(commit_hash)
    if not report:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(report.to_dict())


@app.get("/api/commits")
def api_commits(
    repo: str = Query(".", description="Repository path"),
    branch: str = Query("", description="Branch name (empty for all branches)"),
):
    """Get commits with branch info and analysis status."""
    analyzed = {r["commit"] for r in list_reports(999)}

    # Determine git log scope
    if branch:
        scope = [branch]
    else:
        scope = ["--all"]

    result = subprocess.run(
        ["git", "log", *scope, "--format=%H|%P|%s|%an|%ai"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    if result.returncode != 0:
        return JSONResponse({"error": "not a git repository"}, status_code=400)

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 4)
        h = parts[0]
        parents = parts[1].split() if len(parts) > 1 and parts[1] else []
        commits.append({
            "hash": h,
            "parents": parents,
            "message": parts[2] if len(parts) > 2 else "",
            "author": parts[3] if len(parts) > 3 else "",
            "time": parts[4] if len(parts) > 4 else "",
            "analyzed": h in analyzed,
        })

    # Get branch heads
    branch_result = subprocess.run(
        ["git", "branch", "-a", "--format=%(refname:short)|%(objectname)"],
        capture_output=True, text=True, cwd=repo, timeout=15,
    )
    branches = []
    for line in branch_result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|", 1)
        branches.append({"name": parts[0], "hash": parts[1] if len(parts) > 1 else ""})

    repo_name = Path(repo).resolve().name
    return JSONResponse({"commits": commits, "branches": branches, "repo_name": repo_name})


@app.post("/api/analyze/{commit_hash}")
def api_analyze(commit_hash: str, repo: str = Query(".", description="Repository path"), quick: bool = Query(False)):
    """Trigger analysis for a commit."""
    from review.engine.report_generator import generate_report
    from review.store.report_store import save_report

    try:
        report = generate_report(commit_hash, quick=quick, repo_path=repo)
        save_report(report)
        mode_label = "quick" if quick else "deep" if not quick else "default"
        _log_event(f"分析完成 commit={commit_hash[:12]} mode={mode_label} risk={report.risk_level}")
        return JSONResponse({"status": "ok", "risk_level": report.risk_level, "commit_hash": report.commit_hash})
    except Exception as e:
        _log_event(f"分析失败 commit={commit_hash[:12]} error={e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/diff/{commit_hash}")
def api_get_diff(commit_hash: str, repo: str = Query("."), file: str = Query("")):
    """Get raw diff for a commit, optionally filtered to one file."""
    from review.engine.diff_parser import get_diff
    try:
        diff = get_diff(commit_hash, repo)
        if file:
            lines = []
            capture = False
            for line in diff.split("\n"):
                if line.startswith("diff --git ") and file in line:
                    capture = True
                elif line.startswith("diff --git ") and file not in line:
                    capture = False
                if capture:
                    lines.append(line)
            diff = "\n".join(lines)
        return JSONResponse({"diff": diff, "commit_hash": commit_hash, "file": file or None})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/reports/{commit_hash}/format")
def api_get_report_formatted(commit_hash: str):
    """Return markdown-formatted report for CLI viewing."""
    report = load_report(commit_hash)
    if not report:
        return JSONResponse({"error": "not found"}, status_code=404)
    lines = [
        f"# Review: {report.commit_hash[:12]}",
        f"**{report.commit_message}**",
        f"Author: {report.author} | Risk: **{report.risk_level}**",
        "",
        "## Changes",
    ]
    for c in report.changes:
        lines.append(f"- {c.file} (+{c.added}/-{c.removed})")
    if report.impacts:
        lines.extend(["", "## Impact Analysis"])
        for i in report.impacts:
            lines.append(f"- **{i.symbol}** ({i.risk}) — {len(i.affected_symbols)} affected")
    if report.findings:
        lines.extend(["", "## Findings"])
        for f in report.findings:
            lines.append(f"- [{f.severity}] {f.category}: {f.message}")
    return JSONResponse({"markdown": "\n".join(lines)})


@app.get("/api/reports/{commit_hash}/graphify")
def api_graphify_report(commit_hash: str, repo: str = Query(".")):
    """Generate and return graphify code tree HTML for a commit."""
    from fastapi.responses import FileResponse

    repo_path = Path(repo).resolve()
    graphify_out = repo_path / "graphify-out"
    graphify_out.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["graphify", "update", str(repo_path)],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        pass

    tree_html = graphify_out / "GRAPH_TREE.html"
    try:
        subprocess.run(
            ["graphify", "tree", "--graph", str(graphify_out / "graph.json"),
             "--output", str(tree_html), "--label", repo_path.name],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        pass

    if tree_html.exists():
        return FileResponse(str(tree_html), media_type="text/html")
    return JSONResponse({"error": "graphify output not generated"}, status_code=500)


# ── Launcher API ──────────────────────────────────────────────────────────────

_running_config: dict = {}


class LauncherConfig(BaseModel):
    api_key: str = ""
    model: str = "deepseek-v4-flash"
    host: str = "127.0.0.1"
    port: int = 9090
    repo_path: str = "."
    commit_hash: str = ""
    api_type: str = "deepseek"
    log_dir: str = ""


@app.get("/api/launcher/config")
def api_get_launcher_config():
    """Load persisted launcher config."""
    return JSONResponse(load_config())


@app.post("/api/launcher/config")
def api_save_launcher_config(config: LauncherConfig):
    """Save launcher config."""
    saved = save_config(config.model_dump())
    return JSONResponse(saved)


@app.post("/api/launcher/start")
def api_start_launcher(config: LauncherConfig):
    """One-click launch: install deps -> build -> start server."""
    cfg = save_config(config.model_dump())
    env = get_env_from_config(cfg)
    project_root = Path(__file__).resolve().parent.parent.parent
    web_ui_dir = project_root / "web-ui"

    _log_event("启动流水线开始")

    def _run_pipeline():
        yield json.dumps({"type": "log", "message": "正在安装 Python 依赖...\n"}) + "\n"
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", "."],
                capture_output=True, text=True, timeout=120,
                env=env, cwd=str(project_root),
            )
            if r.returncode != 0:
                yield json.dumps({"type": "error", "message": f"pip install 失败: {r.stderr[-500:]}"}) + "\n"
                return
            yield json.dumps({"type": "log", "message": "Python 依赖安装完成 ✓\n"}) + "\n"
        except subprocess.TimeoutExpired:
            yield json.dumps({"type": "error", "message": "pip install 超时"}) + "\n"
            return

        if web_ui_dir.exists():
            yield json.dumps({"type": "log", "message": "正在安装前端依赖...\n"}) + "\n"
            try:
                r = subprocess.run(
                    ["npm", "install"],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(web_ui_dir), env=env,
                )
                if r.returncode != 0:
                    yield json.dumps({"type": "error", "message": f"npm install 失败: {r.stderr[-500:]}"}) + "\n"
                    return
                yield json.dumps({"type": "log", "message": "前端依赖安装完成 ✓\n"}) + "\n"
            except subprocess.TimeoutExpired:
                yield json.dumps({"type": "error", "message": "npm install 超时"}) + "\n"
                return

            yield json.dumps({"type": "log", "message": "正在构建前端...\n"}) + "\n"
            try:
                r = subprocess.run(
                    ["npm", "run", "build"],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(web_ui_dir), env=env,
                )
                if r.returncode != 0:
                    yield json.dumps({"type": "error", "message": f"前端构建失败: {r.stderr[-500:]}"}) + "\n"
                    return
                yield json.dumps({"type": "log", "message": "前端构建完成 ✓\n"}) + "\n"
            except subprocess.TimeoutExpired:
                yield json.dumps({"type": "error", "message": "前端构建超时"}) + "\n"
                return

        yield json.dumps({
            "type": "ready",
            "message": f"服务已启动! 请访问 http://{cfg['host']}:{cfg['port']}",
            "url": f"http://{cfg['host']}:{cfg['port']}",
        }) + "\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        _run_pipeline(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/shutdown")
def api_shutdown():
    """Shut down the server gracefully."""
    _log_event("服务关闭")
    import threading, os
    def _die():
        import time
        time.sleep(0.3)
        os._exit(0)
    threading.Thread(target=_die, daemon=True).start()
    return JSONResponse({"status": "shutting_down"})


def _mount_static(app: FastAPI):
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and any(static_dir.iterdir()):
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


_mount_static(app)


@app.middleware("http")
async def _spa_fallback(request, call_next):
    """Catch 404 for non-API paths and serve index.html instead."""
    response = await call_next(request)
    if response.status_code == 404 and not request.url.path.startswith("/api/"):
        index_path = Path(__file__).parent / "static" / "index.html"
        if index_path.exists():
            from starlette.responses import FileResponse
            return FileResponse(str(index_path))
    return response


def start_server(host: str = "127.0.0.1", port: int = 9090):
    """Start the FastAPI web server (blocking)."""
    import uvicorn
    import logging

    log_dir_env = os.environ.get("REVIEW_LOG_DIR", "")
    if log_dir_env:
        log_dir = Path(log_dir_env).expanduser().resolve()
    else:
        log_dir = Path.home() / ".review" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"server-{datetime.datetime.now():%Y-%m-%d}.log"
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
    logging.getLogger("uvicorn").addHandler(fh)
    logging.getLogger("uvicorn.access").addHandler(fh)
    logging.getLogger("uvicorn.error").addHandler(fh)

    uvicorn.run(app, host=host, port=port)
