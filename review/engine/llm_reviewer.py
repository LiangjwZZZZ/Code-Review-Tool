import json
import os
from typing import Optional
from review.models import Report, ReviewFinding, DiffChange, ImpactItem


SYSTEM_PROMPT = """你是一个代码审查助手，分析某次提交的影响。
请根据提交的 diff 和 GitNexus 影响分析，输出结构化的审查结果。

每条 finding 包含：
- category: 分类（breaking_change / security / architecture / quality）
- severity: 严重程度（CRITICAL / HIGH / MEDIUM / LOW / INFO）
- message: 问题描述（用中文）
- suggestion: 修复建议（用中文）

分析要点：
1. Breaking changes：函数签名变更、删除导出、类型变化
2. Security：注入风险、鉴权绕过、敏感数据暴露
3. Architecture：耦合增加、循环依赖、分层问题
4. Quality：命名、复杂度、错误处理、测试覆盖影响

所有 message 和 suggestion 请使用中文。
"""


def build_review_prompt(
    commit_message: str,
    changes: list[DiffChange],
    impacts: list[ImpactItem],
    diff_text: str = "",
) -> str:
    """Build prompt for LLM review."""
    lines = [f"Commit: {commit_message}\n"]
    lines.append("## Changes")
    for c in changes:
        lines.append(f"- {c.file}: +{c.added} -{c.removed}")

    if diff_text:
        lines.append("\n## Diff")
        # Truncate very large diffs to avoid token limits
        max_lines = 200
        diff_lines = diff_text.split("\n")
        if len(diff_lines) > max_lines:
            lines.append(f"(显示前 {max_lines} 行，共 {len(diff_lines)} 行)")
            diff_lines = diff_lines[:max_lines]
        for dl in diff_lines:
            lines.append(f"  {dl}")

    lines.append("\n## Impact Analysis")
    for imp in impacts:
        lines.append(f"- {imp.symbol} ({imp.symbol_kind}) in {imp.file}")
        lines.append(f"  Risk: {imp.risk}")
        if imp.affected_symbols:
            lines.append(f"  Affects: {', '.join(imp.affected_symbols[:5])}")

    lines.append("\n## Instructions")
    lines.append("List all review findings as JSON array. Include an 'analysis' finding (severity: INFO)")
    lines.append("that summarizes what this commit does and its overall impact. Format:")
    lines.append('[{"category": "...", "severity": "...", "message": "...", "suggestion": "..."}]')

    return "\n".join(lines)


def _call_deepseek(prompt: str) -> str:
    """Call DeepSeek API (OpenAI-compatible)."""
    import httpx

    api_key = os.environ["DEEPSEEK_API_KEY"]
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2000,
            "temperature": 0.3,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_anthropic(prompt: str, api_key: str) -> str:
    """Call Anthropic Claude API."""
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def run_llm_review(report: Report, api_key: Optional[str] = None, diff_text: str = "") -> list[ReviewFinding]:
    """Run LLM review via DeepSeek or Claude API."""
    prompt = build_review_prompt(report.commit_message, report.changes, report.impacts, diff_text)

    # Priority: DEEPSEEK_API_KEY > ANTHROPIC_API_KEY > fallback
    if os.environ.get("DEEPSEEK_API_KEY"):
        try:
            content = _call_deepseek(prompt)
            return _parse_findings(content)
        except Exception as e:
            return [ReviewFinding(
                category="quality", severity="INFO",
                message=f"DeepSeek 审查失败: {e}",
                suggestion="请检查 DEEPSEEK_API_KEY 和网络连接",
            )]

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        try:
            content = _call_anthropic(prompt, key)
            return _parse_findings(content)
        except Exception as e:
            return [ReviewFinding(
                category="quality", severity="INFO",
                message=f"LLM 审查不可用: {e}",
                suggestion="请设置 ANTHROPIC_API_KEY 或 DEEPSEEK_API_KEY",
            )]

    return _fallback_findings(report)


def _parse_findings(content: str) -> list[ReviewFinding]:
    """Extract ReviewFindings from LLM response."""
    import re

    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if json_match:
        try:
            items = json.loads(json_match.group(0))
            return [ReviewFinding(**item) for item in items]
        except (json.JSONDecodeError, TypeError):
            pass

    findings = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- ") and ":" in line:
            parts = line[2:].split(":", 1)
            findings.append(ReviewFinding(
                category="quality", severity="INFO",
                message=parts[1].strip() if len(parts) > 1 else parts[0],
                suggestion="",
            ))
    return findings


def _fallback_findings(report: Report) -> list[ReviewFinding]:
    """Generate basic findings from diff and impact data without LLM."""
    findings = []
    total_added = sum(c.added for c in report.changes)
    total_removed = sum(c.removed for c in report.changes)

    findings.append(ReviewFinding(
        category="analysis", severity="INFO",
        message=f"本次提交修改了 {len(report.changes)} 个文件：+{total_added}/-{total_removed} 行",
        suggestion=f"请审查 {len(report.changes)} 个修改文件",
    ))

    for imp in report.impacts:
        if imp.risk in ("CRITICAL", "HIGH"):
            findings.append(ReviewFinding(
                category="breaking_change",
                severity=imp.risk,
                message=f"修改 {imp.symbol} 影响 {len(imp.affected_symbols)} 个调用方",
                suggestion="请审查所有受影响调用方并更新用法",
            ))
    if not findings:
        findings.append(ReviewFinding(
            category="quality", severity="INFO",
            message="未检测到高风险变更",
            suggestion="建议常规审查",
        ))
    return findings
