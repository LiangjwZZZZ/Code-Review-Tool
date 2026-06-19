"""混合影响分析：git log -S + javalang AST

三层分析架构：
1. git log -S: 快速查找谁修改过这个方法（秒级）
2. javalang AST: 精确分析调用关系（区分 activityA.setCallback vs activityB.setCallback）
3. 合并结果并评估风险
"""

import subprocess
import re
from pathlib import Path
from typing import Optional
from review.models import ImpactItem


def analyze_hybrid(
    symbols: list[str],
    file_map: dict[str, str],
    repo_path: str = ".",
) -> list[ImpactItem]:
    """混合影响分析主入口

    Args:
        symbols: 要分析的符号列表（方法名/类名）
        file_map: 符号到文件路径的映射
        repo_path: 仓库路径

    Returns:
        影响分析结果列表
    """
    impacts = []

    for symbol in symbols:
        file_path = file_map.get(symbol, "")

        # Layer 1: git log -S 快速查找
        git_impacts = _git_log_analysis(symbol, repo_path)

        # Layer 2: AST 精确分析（只分析变更文件所在目录）
        ast_impacts = _ast_analysis(symbol, file_path, repo_path)

        # 合并结果
        combined = _merge_impacts(git_impacts, ast_impacts, symbol, file_path)
        if combined:
            impacts.append(combined)

    return impacts


def _git_log_analysis(symbol: str, repo_path: str) -> list[dict]:
    """Layer 1: 用 git log -S 查找谁修改过这个方法

    git log -S 会查找添加或删除了指定字符串的 commit。
    """
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-10", f"-S{symbol}", "--", "*.java"],
            capture_output=True, text=True, timeout=10,
            cwd=repo_path
        )
        if result.returncode != 0:
            return []

        callers = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                # 解析 commit hash 和 message
                parts = line.split(" ", 1)
                if len(parts) >= 2:
                    callers.append({
                        "commit": parts[0],
                        "message": parts[1],
                        "type": "git_history"
                    })
        return callers
    except Exception:
        return []


def _ast_analysis(symbol: str, file_path: str, repo_path: str) -> list[dict]:
    """Layer 2: 用 javalang AST 分析调用关系

    只分析变更文件所在目录的 Java 文件，避免全量扫描。
    """
    if not file_path or not file_path.endswith(".java"):
        return []

    try:
        import javalang
    except ImportError:
        return []

    callers = []

    # 只分析变更文件所在目录的同级文件
    file_dir = Path(repo_path) / Path(file_path).parent

    if not file_dir.exists():
        return []

    # 限制扫描范围，避免大 repo 性能问题
    java_files = list(file_dir.glob("*.java"))[:50]  # 最多扫描 50 个文件

    for java_file in java_files:
        try:
            with open(java_file, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()

            # javalang 需要完整 Java 文件，跳过片段
            if not code.strip().endswith("}"):
                continue

            tree = javalang.parse.parse(code)

            # 查找方法调用
            for path, node in tree.filter(javalang.tree.MethodInvocation):
                if node.member == symbol:
                    # 获取调用对象（qualifier）
                    qualifier = node.qualifier or "this"
                    line = node.position.line if node.position else 0
                    callers.append({
                        "file": str(java_file.relative_to(repo_path)),
                        "qualifier": qualifier,
                        "line": line,
                        "type": "ast_call"
                    })

            # 查找方法定义
            for path, node in tree.filter(javalang.tree.MethodDeclaration):
                if node.name == symbol:
                    line = node.position.line if node.position else 0
                    callers.append({
                        "file": str(java_file.relative_to(repo_path)),
                        "qualifier": "definition",
                        "line": line,
                        "type": "ast_definition"
                    })

        except Exception:
            # 解析失败跳过（可能是代码片段或语法错误）
            continue

    return callers


def _merge_impacts(
    git_impacts: list[dict],
    ast_impacts: list[dict],
    symbol: str,
    file_path: str,
) -> Optional[ImpactItem]:
    """合并 git 历史和 AST 分析结果"""
    affected = []

    # 从 git 历史提取（显示谁修改过）
    for g in git_impacts:
        affected.append(f"历史修改: {g['commit']} {g['message'][:40]}")

    # 从 AST 分析提取（显示谁调用了）
    call_count = 0
    for a in ast_impacts:
        if a["type"] == "ast_call":
            affected.append(f"调用方: {a['file']}:{a['line']} {a['qualifier']}.{symbol}()")
            call_count += 1
        elif a["type"] == "ast_definition":
            affected.append(f"定义: {a['file']}:{a['line']}")

    if not affected:
        return None

    # 根据影响范围评估风险
    risk = _assess_risk(call_count, len(git_impacts))

    # 推断符号类型
    kind = "Function"
    if symbol[0].isupper():
        kind = "Class"
    if symbol.startswith("test_"):
        kind = "Test"

    # 构建摘要
    summary_parts = []
    if git_impacts:
        summary_parts.append(f"{len(git_impacts)} 次历史修改")
    if call_count:
        summary_parts.append(f"{call_count} 个调用方")
    summary = ", ".join(summary_parts) if summary_parts else "无影响"

    return ImpactItem(
        symbol=symbol,
        symbol_kind=kind,
        file=file_path,
        risk=risk,
        direction="upstream",
        affected_symbols=affected[:20],
        affected_processes=[],
        summary=summary,
    )


def _assess_risk(call_count: int, history_count: int) -> str:
    """根据调用数量和历史修改次数评估风险"""
    # 调用方越多，风险越高
    if call_count > 10:
        return "CRITICAL"
    elif call_count > 5:
        return "HIGH"
    elif call_count > 2:
        return "MEDIUM"
    elif history_count > 3:
        # 历史修改频繁，可能不稳定
        return "MEDIUM"
    else:
        return "LOW"
