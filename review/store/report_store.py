import json
import sqlite3
from pathlib import Path
from typing import Optional
from review.models import Report, DiffChange, ImpactItem, ReviewFinding


DB_PATH = Path.home() / ".review" / "reports.db"


def _ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            commit_hash TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_report(report: Report):
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT OR REPLACE INTO reports (commit_hash, data, created_at) VALUES (?, ?, ?)",
        (report.commit_hash, json.dumps(report.to_dict()), report.created_at),
    )
    conn.commit()
    conn.close()


def _report_from_dict(data: dict) -> Report:
    """Reconstruct Report with proper nested dataclass instances."""
    data["changes"] = [DiffChange(**c) for c in data.get("changes", [])]
    data["impacts"] = [ImpactItem(**i) for i in data.get("impacts", [])]
    data["findings"] = [ReviewFinding(**f) for f in data.get("findings", [])]
    return Report(**data)


def load_report(commit_hash: str) -> Optional[Report]:
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute(
        "SELECT data FROM reports WHERE commit_hash = ?", (commit_hash,)
    ).fetchone()
    conn.close()
    if row:
        return _report_from_dict(json.loads(row[0]))
    return None


def list_reports(limit: int = 20) -> list[dict]:
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT commit_hash, data, created_at FROM reports ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = json.loads(r[1])
        result.append({
            "commit": r[0],
            "commit_message": d.get("commit_message", ""),
            "commit_body": d.get("commit_body", ""),
            "author": d.get("author", ""),
            "commit_time": d.get("commit_time", ""),
            "repo_name": d.get("repo_name", ""),
            "risk_level": d.get("risk_level", "LOW"),
            "changes_count": len(d.get("changes", [])),
            "created_at": r[2],
        })
    return result
