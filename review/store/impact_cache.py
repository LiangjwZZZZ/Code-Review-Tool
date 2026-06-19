"""SQLite 缓存层，存储影响分析结果

避免重复分析同一个符号，提升大 repo 的分析速度。
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional
from review.models import ImpactItem


DB_PATH = Path.home() / ".review" / "impact_cache.db"


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接，自动创建表"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS impact_cache (
            symbol TEXT,
            repo_path TEXT,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (symbol, repo_path)
        )
    """)
    return conn


def get_cached_impact(symbol: str, repo_path: str) -> Optional[list[ImpactItem]]:
    """获取缓存的影响分析结果

    Args:
        symbol: 方法名/类名
        repo_path: 仓库路径

    Returns:
        缓存的 ImpactItem 列表，如果没有缓存返回 None
    """
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT data FROM impact_cache WHERE symbol=? AND repo_path=?",
            (symbol, repo_path)
        ).fetchone()
        conn.close()

        if row:
            data = json.loads(row[0])
            return [ImpactItem(**item) for item in data]
        return None
    except Exception:
        return None


def cache_impact(symbol: str, repo_path: str, impacts: list[ImpactItem]):
    """缓存影响分析结果

    Args:
        symbol: 方法名/类名
        repo_path: 仓库路径
        impacts: 要缓存的 ImpactItem 列表
    """
    try:
        from dataclasses import asdict
        conn = _get_conn()
        data = json.dumps([asdict(imp) for imp in impacts])
        conn.execute(
            "INSERT OR REPLACE INTO impact_cache (symbol, repo_path, data) VALUES (?, ?, ?)",
            (symbol, repo_path, data)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # 缓存失败不影响主流程


def clear_cache(repo_path: Optional[str] = None):
    """清除缓存

    Args:
        repo_path: 如果指定，只清除该仓库的缓存；否则清除所有
    """
    try:
        conn = _get_conn()
        if repo_path:
            conn.execute("DELETE FROM impact_cache WHERE repo_path=?", (repo_path,))
        else:
            conn.execute("DELETE FROM impact_cache")
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_cache_stats(repo_path: Optional[str] = None) -> dict:
    """获取缓存统计信息

    Returns:
        包含 count 和 size_bytes 的字典
    """
    try:
        conn = _get_conn()
        if repo_path:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(LENGTH(data)), 0) FROM impact_cache WHERE repo_path=?",
                (repo_path,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(LENGTH(data)), 0) FROM impact_cache"
            ).fetchone()
        conn.close()
        return {"count": row[0], "size_bytes": row[1]}
    except Exception:
        return {"count": 0, "size_bytes": 0}
