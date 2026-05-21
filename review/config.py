import json
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".review"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "deepseek-v4-flash",
    "host": "127.0.0.1",
    "port": 9090,
    "repo_path": ".",
    "commit_hash": "",
    "api_type": "deepseek",
    "log_dir": "",
    "repos": [],
    "current_repo": "",
    "global_branch": "",
    "per_repo_branches": {},
    "gerrit_url": "",
    "gerrit_repo_map": {},
}


def _ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    _ensure_dir()
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            return {**DEFAULT_CONFIG, **data}
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> dict:
    _ensure_dir()
    merged = {**DEFAULT_CONFIG, **config}
    CONFIG_FILE.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    return merged


def get_log_dir(config: dict) -> Path:
    """Get the effective log directory, defaulting to ~/.review/logs/."""
    d = config.get("log_dir") or str(CONFIG_DIR / "logs")
    p = Path(d).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_env_from_config(config: dict) -> dict:
    """Map launcher config to environment variables for subprocess."""
    env = dict(os.environ)
    if config.get("api_key"):
        if config.get("api_type") == "anthropic":
            env["ANTHROPIC_API_KEY"] = config["api_key"]
        else:
            env["DEEPSEEK_API_KEY"] = config["api_key"]
    return env
