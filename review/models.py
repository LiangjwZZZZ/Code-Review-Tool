from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class DiffChange:
    file: str
    added: int
    removed: int
    hunks: list[str]


@dataclass
class ImpactItem:
    symbol: str
    symbol_kind: str  # Function, Class, Method, etc.
    file: str
    risk: str  # CRITICAL / HIGH / MEDIUM / LOW
    direction: str  # upstream, downstream
    affected_symbols: list[str] = field(default_factory=list)
    affected_processes: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ReviewFinding:
    category: str  # breaking_change / security / architecture / quality
    severity: str  # CRITICAL / HIGH / MEDIUM / LOW / INFO
    message: str
    suggestion: str = ""


@dataclass
class FileAnalysis:
    file: str
    diff_text: str
    impacts: list[ImpactItem] = field(default_factory=list)
    findings: list[ReviewFinding] = field(default_factory=list)
    module: str = ""
    analysis_status: str = "pending"  # pending | completed | error


@dataclass
class Report:
    commit_hash: str
    commit_message: str
    author: str
    risk_level: str  # CRITICAL / HIGH / MEDIUM / LOW
    commit_body: str = ""
    commit_time: str = ""
    repo_name: str = ""
    changes: list[DiffChange] = field(default_factory=list)
    impacts: list[ImpactItem] = field(default_factory=list)
    findings: list[ReviewFinding] = field(default_factory=list)
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    file_analyses: list[FileAnalysis] = field(default_factory=list)
    cross_module_impacts: list[dict] = field(default_factory=list)
    modules: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
