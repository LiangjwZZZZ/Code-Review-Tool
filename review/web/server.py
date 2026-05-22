import datetime
import json
import os
import re
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from review.config import load_config, save_config, get_env_from_config, get_log_dir
from review.store.report_store import load_report, list_reports
from review.gerrit import parse_gerrit_url, get_refspec, get_latest_patchset, match_repo_to_gerrit


from review.engine.diff_parser import get_diff, parse_diff, get_commit_info


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


_PSEUDO_BRANCH_LABEL = re.compile(r"^\(HEAD detached (?:at|from) .+\)$|^\(no branch\)$")


def _is_detached_head_label(name: str) -> bool:
    """True when git branch --format returns detached pseudo-branch label."""
    return bool(_PSEUDO_BRANCH_LABEL.match(name.strip()))


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
    if branch and not _is_detached_head_label(branch):
        scope = [branch]
    else:
        scope = ["--all"]

    result = subprocess.run(
        ["git", "log", *scope, "--format=%H|%P|%s|%an|%ai"],
        capture_output=True, text=True, cwd=repo, timeout=30,
    )
    if result.returncode != 0:
        return JSONResponse(
            {"error": "invalid branch" if branch else "not a git repository"},
            status_code=400,
        )

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
        name = parts[0]
        if _is_detached_head_label(name):
            continue
        branches.append({"name": name, "hash": parts[1] if len(parts) > 1 else ""})

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
        mode_label = "quick" if quick else "default"
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


@app.get("/api/commits/{commit_hash}/preview")
def api_commit_preview(commit_hash: str, repo: str = Query(".")):
    """Return commit info + changed files without full analysis."""
    try:
        info = get_commit_info(commit_hash, repo)
        diff_text = get_diff(commit_hash, repo)
        changes = parse_diff(diff_text)
        return JSONResponse({
            "hash": info["hash"],
            "message": info["message"],
            "body": info.get("body", ""),
            "author": info["author"],
            "time": info.get("time", ""),
            "changes": [
                {"file": c.file, "added": c.added, "removed": c.removed, "hunks": c.hunks}
                for c in changes
            ],
        })
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


@app.post("/api/reports/{commit_hash}/analyze-file")
def api_analyze_file(
    commit_hash: str,
    file: str = Query(...),
    repo: str = Query("."),
):
    """Run LLM review on a single file's changes and update the report."""
    from review.engine.llm_reviewer import run_file_llm_review

    report = load_report(commit_hash)
    if not report:
        return JSONResponse({"error": "not found"}, status_code=404)

    # Find matching FileAnalysis
    fa = None
    for f in report.file_analyses:
        if f.file == file:
            fa = f
            break

    if not fa:
        return JSONResponse({"error": f"file '{file}' not found in report"}, status_code=404)

    # Run per-file LLM review
    findings = run_file_llm_review(
        file_path=fa.file,
        module=fa.module,
        diff_text=fa.diff_text,
        impacts=fa.impacts,
    )

    fa.findings = findings
    fa.analysis_status = "completed" if findings else "error"

    # Persist updated report
    save_report(report)

    return JSONResponse({
        "findings": [f.__dict__ for f in findings],
        "analysis_status": fa.analysis_status,
    })


@app.get("/api/reports/{commit_hash}/modules")
def api_get_modules(commit_hash: str):
    """Return module info and cross-module impacts for a report."""
    report = load_report(commit_hash)
    if not report:
        return JSONResponse({"error": "not found"}, status_code=404)

    file_modules = {}
    for fa in report.file_analyses:
        file_modules[fa.file] = fa.module

    return JSONResponse({
        "modules": report.modules,
        "cross_module_impacts": report.cross_module_impacts,
        "file_modules": file_modules,
    })


# ── Gerrit integration ─────────────────────────────────────────────────────────


@app.post("/api/gerrit/analyze")
def api_gerrit_analyze(
    gerrit_url: str = Query(..., description="Gerrit change URL"),
    repo: str = Query("", description="Override local repo path"),
):
    """Fetch a Gerrit change and run analysis on it.

    Flow: parse URL → match local repo → git fetch → generate_report → save.
    """
    from review.engine.report_generator import generate_report
    from review.store.report_store import save_report

    cfg = load_config()
    parsed = parse_gerrit_url(gerrit_url)

    # Determine which local repo to use
    if repo:
        repo_path = repo
    else:
        repos_list = cfg.get("repos", []) or []
        current = cfg.get("current_repo", "")
        candidates = repos_list if repos_list else ([current] if current else [])

        matched = match_repo_to_gerrit(
            parsed["host"], parsed["project"],
            candidates,
            cfg.get("gerrit_repo_map", {}),
        )
        if not matched:
            matched = current or cfg.get("repo_path", ".")
        repo_path = matched

    patchset = parsed["patchset"]
    if patchset is None:
        patchset = get_latest_patchset(
            parsed["host"], parsed["change"],
            username=cfg.get("gerrit_username") or None,
            password=cfg.get("gerrit_password") or None,
        )
    if patchset is None:
        return JSONResponse({
            "error": "No patchset specified and could not query Gerrit API for the latest patchset. "
                     "Please configure Gerrit credentials in settings or append the patchset number to the URL (e.g. .../+/106779/3)."
        }, status_code=400)

    refspec = get_refspec(parsed["change"], patchset)

    try:
        fetch_result = subprocess.run(
            ["git", "fetch", "origin", refspec],
            capture_output=True, text=True, cwd=repo_path,
            timeout=30,
        )
        if fetch_result.returncode != 0:
            return JSONResponse({
                "error": f"git fetch failed: {fetch_result.stderr[:500]}",
            }, status_code=400)

        rev_result = subprocess.run(
            ["git", "rev-parse", "FETCH_HEAD"],
            capture_output=True, text=True, cwd=repo_path,
            timeout=10,
        )
        if rev_result.returncode != 0:
            return JSONResponse({
                "error": f"Failed to resolve FETCH_HEAD: {rev_result.stderr[:200]}",
            }, status_code=500)
        commit_hash = rev_result.stdout.strip()

        report = generate_report(commit_hash, repo_path=repo_path)
        save_report(report)

        _log_event(
            f"Gerrit分析完成 change={parsed['change']} patchset={parsed['patchset']} "
            f"commit={commit_hash[:12]} repo={Path(repo_path).name}"
        )

        return JSONResponse({
            "status": "ok",
            "commit_hash": report.commit_hash,
            "risk_level": report.risk_level,
            "report_url": f"/report/{report.commit_hash}?repo={repo_path}",
        })
    except Exception as e:
        _log_event(f"Gerrit分析失败 change={parsed['change']} error={e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Repo manifest detection ───────────────────────────────────────────────────

def _detect_repos_from_manifest(root_path: str) -> list[str]:
    """Detect git repos from .repo/manifest.xml (Android repo tool format).
    Returns list of full paths to each project in the manifest, or empty list.
    """
    repo_dir = Path(root_path) / ".repo"
    if not repo_dir.is_dir():
        return []

    manifest_file = repo_dir / "manifest.xml"
    if not manifest_file.exists():
        # Try manifests/default.xml as fallback
        manifest_file = repo_dir / "manifests" / "default.xml"
    if not manifest_file.exists():
        return []

    try:
        tree = ET.parse(manifest_file)
        root = tree.getroot()

        repos = []
        for project in root.findall("project"):
            path = project.get("path")
            if path:
                repos.append(str(Path(root_path) / path))

        # Handle <include> elements (relative to manifest dir)
        parent = manifest_file.parent
        for inc in root.findall("include"):
            inc_name = inc.get("name")
            if not inc_name:
                continue
            inc_path = parent / inc_name
            if inc_path.exists():
                try:
                    inc_tree = ET.parse(inc_path)
                    inc_root = inc_tree.getroot()
                    for project in inc_root.findall("project"):
                        path = project.get("path")
                        if path:
                            repos.append(str(Path(root_path) / path))
                except (ET.ParseError, OSError):
                    pass

        return sorted(set(repos))
    except (ET.ParseError, OSError):
        return []


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
    repos: list[str] = []
    current_repo: str = ""
    global_branch: str = ""
    per_repo_branches: dict[str, str] = {}
    gerrit_username: str = ""
    gerrit_password: str = ""


def _derive_repos(cfg: dict) -> dict:
    """Derive repos list from repo_path (no persistence)."""
    cfg = dict(cfg)  # don't mutate caller's dict
    rp = cfg.get("repo_path", "")
    if rp and rp != ".":
        detected = _detect_repos_from_manifest(rp)
        cfg["repos"] = detected if detected else [rp]
    else:
        cfg["repos"] = []
    return cfg


@app.get("/api/launcher/config")
def api_get_launcher_config():
    """Load persisted launcher config."""
    cfg = load_config()
    return JSONResponse(_derive_repos(cfg))


@app.post("/api/launcher/config")
def api_save_launcher_config(config: LauncherConfig):
    """Save launcher config."""
    data = config.model_dump()
    # Strip repos — it's derived, not persisted
    data.pop("repos", None)

    rp = data.get("repo_path", "")
    if rp and rp != ".":
        detected = _detect_repos_from_manifest(rp)
        if detected:
            cr = data.get("current_repo", "")
            if cr and cr not in detected:
                data["current_repo"] = ""
        else:
            data["current_repo"] = ""

    saved = save_config(data)
    return JSONResponse(_derive_repos(saved))


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
    # When packaged with PyInstaller, static files are extracted to sys._MEIPASS/static
    if getattr(sys, "frozen", False):
        static_dir = Path(sys._MEIPASS) / "static"  # type: ignore[attr-defined]
    else:
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
