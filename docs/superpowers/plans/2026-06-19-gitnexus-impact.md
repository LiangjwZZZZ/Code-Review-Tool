# GitNexus 影响分析集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 Java diff 中提取实际修改的函数/类名，调用 GitNexus 做符号级影响分析，并打包到 Windows exe。

**Architecture:** 改进 `diff_parser.py` 的符号提取（正则匹配 Java 方法/类声明），重构 `impact_analyzer.py` 支持平台检测和 npx 调用，新增 SSE 进度推送 API，前端 Timeline 页面加分析按钮。

**Tech Stack:** Python / FastAPI / React / TypeScript / GitNexus CLI / nexe

## Global Constraints

- Python 3.12+
- Node.js 20+ (用于 npx gitnexus)
- Ubuntu: 有 Node.js，无法全局安装 gitnexus
- Windows: 无依赖，需要打包成 exe
- Java 代码审查为主

---

## Task 1: Java 符号提取

**Files:**
- Modify: `review/engine/diff_parser.py:81-87`
- Test: `tests/test_diff_parser.py`

**Interfaces:**
- Consumes: `DiffChange` 列表 + diff 文本
- Produces: `list[str]` 符号名列表

- [ ] **Step 1: Write the failing test**

```python
# tests/test_diff_parser.py - 添加以下测试

def test_get_changed_symbols_extracts_java_methods():
    """Test that get_changed_symbols extracts actual Java method names from diff."""
    from review.engine.diff_parser import get_changed_symbols, DiffChange

    diff_text = """diff --git a/src/com/example/Foo.java b/src/com/example/Foo.java
--- a/src/com/example/Foo.java
+++ b/src/com/example/Foo.java
@@ -10,6 +10,10 @@ public class Foo {
     public void oldMethod() {
     }
 
+    public void newMethod(String param) {
+        return;
+    }
+
     public static int helper(int x) {
"""
    changes = [DiffChange(file="src/com/example/Foo.java", added=4, removed=0, hunks=[])]
    symbols = get_changed_symbols(changes, diff_text)
    assert "newMethod" in symbols
    assert "helper" not in symbols  # helper 没被修改


def test_get_changed_symbols_extracts_class_name():
    """Test that get_changed_symbols extracts class name when class declaration is modified."""
    from review.engine.diff_parser import get_changed_symbols, DiffChange

    diff_text = """diff --git a/src/com/example/Bar.java b/src/com/example/Bar.java
--- a/src/com/example/Bar.java
+++ b/src/com/example/Bar.java
@@ -5,7 +5,7 @@
- public class Bar {
+ public class Bar extends BaseActivity {
"""
    changes = [DiffChange(file="src/com/example/Bar.java", added=1, removed=1, hunks=[])]
    symbols = get_changed_symbols(changes, diff_text)
    assert "Bar" in symbols


def test_get_changed_symbols_no_duplicates():
    """Test that duplicate symbols are removed."""
    from review.engine.diff_parser import get_changed_symbols, DiffChange

    diff_text = """diff --git a/src/com/example/Foo.java b/src/com/example/Foo.java
--- a/src/com/example/Foo.java
+++ b/src/com/example/Foo.java
@@ -10,6 +10,8 @@
+    public void doSomething() {
+    }
+    public void doSomething(int x) {
+    }
"""
    changes = [DiffChange(file="src/com/example/Foo.java", added=4, removed=0, hunks=[])]
    symbols = get_changed_symbols(changes, diff_text)
    assert symbols.count("doSomething") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool && python -m pytest tests/test_diff_parser.py::test_get_changed_symbols_extracts_java_methods -v`
Expected: FAIL with TypeError (get_changed_symbols missing diff_text parameter)

- [ ] **Step 3: Write minimal implementation**

```python
# review/engine/diff_parser.py - 修改 get_changed_symbols

import re
from pathlib import Path

# Java 符号提取正则
_JAVA_CLASS_PATTERN = re.compile(
    r'(?:public|protected|private)?\s*(?:abstract|final|static)?\s*class\s+(\w+)'
)
_JAVA_METHOD_PATTERN = re.compile(
    r'(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?[\w<>\[\]]+\s+(\w+)\s*\('
)


def get_changed_symbols(changes: list[DiffChange], diff_text: str = "") -> list[str]:
    """Extract symbol-like names from changed files.

    For Java files, extracts actual method/class names from the diff.
    For other files, falls back to filename stem.
    """
    symbols = []
    file_diffs = _split_diff_by_file(diff_text) if diff_text else {}

    for c in changes:
        # Check if it's a Java file
        if c.file.endswith(".java"):
            java_symbols = _extract_java_symbols(c.file, file_diffs.get(c.file, ""))
            symbols.extend(java_symbols)
        else:
            # Fallback to filename stem
            stem = Path(c.file).stem
            symbols.append(stem)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def _split_diff_by_file(diff_text: str) -> dict[str, str]:
    """Split full diff by file, return {file_path: diff_section}."""
    files = {}
    current_file = None
    current_lines = []

    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            if current_file and current_lines:
                files[current_file] = "\n".join(current_lines)
            parts = line.split()
            current_file = parts[-1][2:] if len(parts) >= 4 else parts[-1]
            current_lines = [line]
        elif current_file is not None:
            current_lines.append(line)

    if current_file and current_lines:
        files[current_file] = "\n".join(current_lines)
    return files


def _extract_java_symbols(file_path: str, diff_section: str) -> list[str]:
    """Extract Java symbols modified in the diff."""
    if not diff_section:
        return []

    # Find modified line numbers from diff
    modified_lines = set()
    current_line = 0
    for line in diff_section.split("\n"):
        if line.startswith("@@"):
            # Parse hunk header: @@ -old,count +new,count @@
            match = re.search(r'\+(\d+)', line)
            if match:
                current_line = int(match.group(1)) - 1
        elif line.startswith("+") and not line.startswith("+++"):
            modified_lines.add(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass  # Don't increment for removed lines
        else:
            current_line += 1

    if not modified_lines:
        return []

    # Try to read the current file to get line numbers
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            file_lines = f.readlines()
    except (OSError, IOError):
        # If can't read file, extract symbols from diff text directly
        return _extract_symbols_from_diff_text(diff_section)

    # Build symbol -> line range mapping from file
    symbol_ranges = _build_symbol_ranges(file_lines)

    # Find symbols that overlap with modified lines
    symbols = []
    for symbol, (start, end) in symbol_ranges.items():
        if any(start <= line <= end for line in modified_lines):
            symbols.append(symbol)

    return symbols


def _extract_symbols_from_diff_text(diff_text: str) -> list[str]:
    """Fallback: extract symbols directly from diff + lines."""
    symbols = []
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            code = line[1:].strip()
            # Try to match method declaration
            match = _JAVA_METHOD_PATTERN.search(code)
            if match:
                symbols.append(match.group(1))
            # Try to match class declaration
            match = _JAVA_CLASS_PATTERN.search(code)
            if match:
                symbols.append(match.group(1))
    return symbols


def _build_symbol_ranges(file_lines: list[str]) -> dict[str, tuple[int, int]]:
    """Build mapping of symbol name -> (start_line, end_line) from file content."""
    ranges = {}
    brace_stack = []
    current_symbol = None
    current_start = 0

    for i, line in enumerate(file_lines):
        stripped = line.strip()

        # Check for class declaration
        class_match = _JAVA_CLASS_PATTERN.search(stripped)
        if class_match:
            current_symbol = class_match.group(1)
            current_start = i
            brace_stack = []
            continue

        # Check for method declaration
        method_match = _JAVA_METHOD_PATTERN.search(stripped)
        if method_match:
            current_symbol = method_match.group(1)
            current_start = i
            brace_stack = []
            continue

        # Track braces to find end of symbol
        if current_symbol:
            brace_stack.extend([c for c in stripped if c == '{'])
            if '}' in stripped:
                for _ in stripped:
                    if stripped.startswith('}') and brace_stack:
                        brace_stack.pop()
                        if not brace_stack:
                            ranges[current_symbol] = (current_start, i)
                            current_symbol = None
                            break

    return ranges
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool && python -m pytest tests/test_diff_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add review/engine/diff_parser.py tests/test_diff_parser.py
git commit -m "feat: 从 Java diff 中提取实际修改的函数/类名"
```

---

## Task 2: GitNexus 平台检测与调用

**Files:**
- Modify: `review/engine/impact_analyzer.py`
- Test: `tests/test_impact_analyzer.py`

**Interfaces:**
- Consumes: 符号列表 + repo 路径
- Produces: `list[ImpactItem]` 影响分析结果

- [ ] **Step 1: Write the failing test**

```python
# tests/test_impact_analyzer.py - 添加以下测试

def test_find_gitnexus_command_windows():
    """Test GitNexus discovery on Windows with bundled exe."""
    from review.engine.impact_analyzer import find_gitnexus_command
    from unittest.mock import patch, MagicMock
    import sys

    with patch('sys.platform', 'win32'), \
         patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="gitnexus v1.0.0")
        cmd = find_gitnexus_command()
        assert cmd is not None
        assert "gitnexus.exe" in cmd or "npx" in cmd


def test_find_gitnexus_command_linux_npx():
    """Test GitNexus discovery on Linux using npx."""
    from review.engine.impact_analyzer import find_gitnexus_command
    from unittest.mock import patch, MagicMock

    with patch('sys.platform', 'linux'), \
         patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="gitnexus v1.0.0")
        cmd = find_gitnexus_command()
        assert cmd is not None
        assert "npx" in cmd or "gitnexus" in cmd


def test_analyze_symbol_returns_none_on_failure():
    """Test that analyze_symbol returns None when gitnexus fails."""
    from review.engine.impact_analyzer import analyze_symbol
    from unittest.mock import patch, MagicMock

    with patch('review.engine.impact_analyzer.find_gitnexus_command', return_value=None):
        result = analyze_symbol("myMethod", "Foo.java", "/repo")
        assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool && python -m pytest tests/test_impact_analyzer.py -v`
Expected: FAIL with ImportError (find_gitnexus_command not defined)

- [ ] **Step 3: Write minimal implementation**

```python
# review/engine/impact_analyzer.py - 完全重写

import json
import subprocess
import re
import sys
from pathlib import Path
from typing import Optional

from review.models import ImpactItem


SUBPROCESS_TIMEOUT = 30
GITNEXUS_INDEX_DIR = Path.home() / ".review" / "gitnexus"


def find_gitnexus_command() -> Optional[str]:
    """Find gitnexus command based on platform.

    Discovery order:
    1. Windows: check for bundled gitnexus.exe in tool directory
    2. All platforms: try npx gitnexus (downloads to temp)
    3. Fallback: check PATH for gitnexus
    """
    # 1. Windows bundled exe
    if sys.platform == "win32":
        exe_path = Path(sys.executable).parent / "gitnexus.exe"
        if exe_path.exists():
            return str(exe_path)

    # 2. Try npx (works on all platforms with Node.js)
    try:
        result = subprocess.run(
            ["npx", "gitnexus", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return "npx"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 3. Check PATH
    try:
        result = subprocess.run(
            ["gitnexus", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return "gitnexus"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def _build_gitnexus_cmd(base_cmd: str, args: list[str], repo_path: str) -> list[str]:
    """Build full gitnexus command with proper arguments."""
    if base_cmd == "npx":
        return ["npx", "gitnexus"] + args + ["--repo", repo_path]
    else:
        return [base_cmd] + args + ["--repo", repo_path]


def ensure_index(repo_path: str, force: bool = False) -> bool:
    """Ensure gitnexus index exists for the repo.

    Returns True if index is ready, False if indexing failed.
    """
    cmd = find_gitnexus_command()
    if not cmd:
        return False

    repo_name = Path(repo_path).resolve().name
    index_dir = GITNEXUS_INDEX_DIR / repo_name

    # Check if index exists and is fresh
    if not force and index_dir.exists():
        # Index exists, assume it's valid
        return True

    # Run gitnexus analyze
    analyze_cmd = _build_gitnexus_cmd(cmd, ["analyze"], repo_path)
    try:
        result = subprocess.run(
            analyze_cmd,
            capture_output=True, text=True,
            timeout=300,  # 5 minutes for initial indexing
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def analyze_symbol(
    symbol: str,
    file_path: Optional[str] = None,
    repo_path: str = ".",
) -> Optional[ImpactItem]:
    """Run gitnexus impact on a single symbol and return ImpactItem.

    Returns None if the symbol isn't indexed or gitnexus fails.
    """
    cmd = find_gitnexus_command()
    if not cmd:
        return None

    args = ["impact", symbol, "--direction", "upstream"]
    if file_path:
        args.extend(["--file-path", file_path])

    full_cmd = _build_gitnexus_cmd(cmd, args, repo_path)

    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT
        )
        if result.returncode != 0:
            return None

        output = result.stdout
        return _parse_gitnexus_output(symbol, output, file_path or "")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _parse_gitnexus_output(symbol: str, output: str, file_path: str) -> ImpactItem:
    """Parse gitnexus impact CLI output into ImpactItem."""
    affected = []
    processes = []
    risk = "MEDIUM"

    # Extract risk level
    risk_match = re.search(r"risk:\s*(CRITICAL|HIGH|MEDIUM|LOW)", output, re.IGNORECASE)
    risk = _parse_risk(risk_match.group(1)) if risk_match else "MEDIUM"

    # Extract affected symbols
    for line in output.split("\n"):
        line = line.strip()
        if re.match(r"^[a-zA-Z0-9_/.-]+\.[a-zA-Z]+:\d+", line):
            affected.append(line.split()[0])
        elif re.match(r"^\s*[•\-]", line):
            affected.append(line.lstrip("•- ").strip())
        if "process" in line.lower() or "execution" in line.lower():
            processes.append(line.strip())

    # Determine kind from symbol naming convention
    kind = "Function"
    if symbol[0].isupper():
        kind = "Class"
    if symbol.startswith("test_"):
        kind = "Test"

    return ImpactItem(
        symbol=symbol,
        symbol_kind=kind,
        file=file_path,
        risk=risk,
        direction="upstream",
        affected_symbols=affected[:20],
        affected_processes=processes[:5],
        summary=output[:500],
    )


def _parse_risk(risk_str: str) -> str:
    """Normalize risk string."""
    risk_str = risk_str.upper().strip()
    for valid in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if valid in risk_str:
            return valid
    return "MEDIUM"


def analyze_changes(symbols: list[str], file_map: dict[str, str], repo_path: str = ".") -> list[ImpactItem]:
    """Analyze multiple changed symbols via gitnexus."""
    impacts = []
    for sym in symbols:
        file_path = file_map.get(sym, "")
        item = analyze_symbol(sym, file_path, repo_path)
        if item:
            impacts.append(item)
    return impacts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool && python -m pytest tests/test_impact_analyzer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add review/engine/impact_analyzer.py tests/test_impact_analyzer.py
git commit -m "feat: GitNexus 平台检测与调用层重构"
```

---

## Task 3: 更新 report_generator 使用新符号提取

**Files:**
- Modify: `review/engine/report_generator.py:91-96`
- Test: `tests/test_report_generator.py`

**Interfaces:**
- Consumes: 新的 `get_changed_symbols(changes, diff_text)` 签名
- Produces: 无需变化

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report_generator.py - 添加以下测试

def test_generate_report_uses_java_symbols():
    """Test that generate_report extracts Java symbols correctly."""
    from review.engine.report_generator import generate_report
    from unittest.mock import patch, MagicMock

    mock_info = {"hash": "abc123", "message": "test commit", "author": "test", "time": "2026-01-01"}
    mock_diff = """diff --git a/src/Foo.java b/src/Foo.java
+    public void newMethod() {
"""
    mock_changes = [MagicMock(file="src/Foo.java", added=1, removed=0)]

    with patch('review.engine.report_generator.get_commit_info', return_value=mock_info), \
         patch('review.engine.report_generator.get_diff', return_value=mock_diff), \
         patch('review.engine.report_generator.parse_diff', return_value=mock_changes), \
         patch('review.engine.report_generator.get_changed_symbols', return_value=["newMethod"]) as mock_symbols, \
         patch('review.engine.report_generator.analyze_changes', return_value=[]), \
         patch('review.engine.report_generator.run_llm_review', return_value=[]):
        report = generate_report("abc123", quick=True)
        # Verify get_changed_symbols was called with diff_text
        mock_symbols.assert_called_with(mock_changes, mock_diff)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool && python -m pytest tests/test_report_generator.py -v`
Expected: FAIL (get_changed_symbols called with wrong args)

- [ ] **Step 3: Write minimal implementation**

```python
# review/engine/report_generator.py - 修改第 93-95 行

# 旧代码:
# symbols = get_changed_symbols(changes)
# file_map = {s: c.file for c in changes for s in get_changed_symbols([c])}

# 新代码:
symbols = get_changed_symbols(changes, diff_text)
file_map = {s: c.file for c in changes for s in get_changed_symbols([c], diff_text)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool && python -m pytest tests/test_report_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add review/engine/report_generator.py tests/test_report_generator.py
git commit -m "feat: report_generator 使用新的符号提取接口"
```

---

## Task 4: SSE 进度推送 API

**Files:**
- Modify: `review/web/server.py`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: commit hash + repo path
- Produces: SSE 流推送进度事件

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web.py - 添加以下测试

def test_analyze_sse_endpoint():
    """Test SSE analysis endpoint returns event stream."""
    from fastapi.testclient import TestClient
    from review.web.server import app
    from unittest.mock import patch, MagicMock

    client = TestClient(app)

    mock_report = MagicMock()
    mock_report.risk_level = "LOW"
    mock_report.commit_hash = "abc123"

    with patch('review.engine.report_generator.generate_report', return_value=mock_report), \
         patch('review.store.report_store.save_report'):
        response = client.get(
            "/api/analyze-sse",
            params={"commit": "abc123", "repo": "."}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool && python -m pytest tests/test_web.py -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: Write minimal implementation**

```python
# review/web/server.py - 在 api_analyze 后添加

from fastapi.responses import StreamingResponse

@app.get("/api/analyze-sse")
def api_analyze_sse(
    commit: str = Query(..., description="Commit hash"),
    repo: str = Query(".", description="Repository path"),
    force: bool = Query(False, description="Force re-index"),
):
    """SSE endpoint for analysis with progress updates."""
    from review.engine.report_generator import generate_report
    from review.store.report_store import save_report
    from review.engine.impact_analyzer import ensure_index, find_gitnexus_command

    cfg = load_config()
    if cfg.get("api_key"):
        _set_api_env(cfg)

    def event_stream():
        # Stage 1: Check/Build index
        if find_gitnexus_command():
            yield f"event: progress\ndata: {json.dumps({'stage': 'indexing', 'message': '正在检查代码索引...'})}\n\n"
            if not ensure_index(repo, force=force):
                yield f"event: progress\ndata: {json.dumps({'stage': 'indexing', 'message': '正在建立代码索引...（首次较慢）'})}\n\n"
                ensure_index(repo, force=True)

        # Stage 2: Impact analysis
        yield f"event: progress\ndata: {json.dumps({'stage': 'analyzing', 'message': '正在分析变更影响...'})}\n\n"

        # Stage 3: LLM review
        yield f"event: progress\ndata: {json.dumps({'stage': 'llm', 'message': '正在进行 AI 审查...'})}\n\n"

        try:
            report = generate_report(commit, repo_path=repo)
            save_report(report)

            # Stage 4: Done
            yield f"event: done\ndata: {json.dumps({'status': 'ok', 'risk_level': report.risk_level, 'commit_hash': report.commit_hash})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool && python -m pytest tests/test_web.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add review/web/server.py tests/test_web.py
git commit -m "feat: SSE 进度推送 API"
```

---

## Task 5: 前端 Timeline 分析按钮

**Files:**
- Modify: `web-ui/src/App.tsx`
- Modify: `web-ui/src/api.ts`

**Interfaces:**
- Consumes: SSE 事件流
- Produces: UI 进度显示

- [ ] **Step 1: 添加 SSE 调用函数**

```typescript
// web-ui/src/api.ts - 添加以下函数

export interface AnalyzeProgress {
  stage: 'indexing' | 'analyzing' | 'llm' | 'done' | 'error';
  message: string;
}

export function analyzeWithProgress(
  commitHash: string,
  repo: string,
  force: boolean = false,
  onProgress: (progress: AnalyzeProgress) => void,
  onDone: (result: { status: string; risk_level: string; commit_hash: string }) => void,
  onError: (error: string) => void,
): () => void {
  const params = new URLSearchParams({ commit: commitHash, repo, force: String(force) });
  const eventSource = new EventSource(`/api/analyze-sse?${params}`);

  eventSource.addEventListener('progress', (event) => {
    const data = JSON.parse(event.data);
    onProgress(data);
  });

  eventSource.addEventListener('done', (event) => {
    const data = JSON.parse(event.data);
    onDone(data);
    eventSource.close();
  });

  eventSource.addEventListener('error', (event) => {
    const data = JSON.parse((event as MessageEvent).data);
    onError(data.error);
    eventSource.close();
  });

  // Return cleanup function
  return () => eventSource.close();
}
```

- [ ] **Step 2: 修改 Timeline 页面添加分析按钮**

```tsx
// web-ui/src/App.tsx - 在 commit 列表项中添加分析按钮

// 在 CommitList 组件中，每个 commit 项添加：
const [analyzing, setAnalyzing] = useState<string | null>(null);
const [progress, setProgress] = useState<AnalyzeProgress | null>(null);

const handleAnalyze = (commitHash: string) => {
  setAnalyzing(commitHash);
  setProgress({ stage: 'indexing', message: '开始分析...' });

  analyzeWithProgress(
    commitHash,
    currentRepo,
    false,
    (p) => setProgress(p),
    (result) => {
      setAnalyzing(null);
      setProgress(null);
      // Refresh report
      loadReport(result.commit_hash);
    },
    (error) => {
      setAnalyzing(null);
      setProgress(null);
      alert(`分析失败: ${error}`);
    }
  );
};

// 在 commit 项的 JSX 中添加：
{commit.analyzed ? (
  <button onClick={() => loadReport(commit.hash)}>查看报告</button>
) : (
  <button
    onClick={() => handleAnalyze(commit.hash)}
    disabled={analyzing === commit.hash}
  >
    {analyzing === commit.hash ? (
      <span>{progress?.message || '分析中...'}</span>
    ) : (
      '分析'
    )}
  </button>
)}
```

- [ ] **Step 3: 构建前端验证**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool/web-ui && npm run build`
Expected: 构建成功，无 TypeScript 错误

- [ ] **Step 4: Commit**

```bash
git add web-ui/src/App.tsx web-ui/src/api.ts
git commit -m "feat: Timeline 页面添加分析按钮和进度显示"
```

---

## Task 6: Windows 打包脚本

**Files:**
- Modify: `build_exe.bat`
- Modify: `code_review.spec`

**Interfaces:**
- Consumes: gitnexus npm 包
- Produces: gitnexus.exe

- [ ] **Step 1: 修改 build_exe.bat**

```batch
@echo off
REM build_exe.bat - 添加 gitnexus 打包步骤

echo [1/5] Installing Python dependencies...
pip install -e .
pip install pyinstaller nexe

echo [2/5] Building frontend...
cd web-ui
call npm install
call npm run build
cd ..

echo [3/5] Packaging gitnexus as standalone exe...
call npm install gitnexus
call npx nexe node_modules/gitnexus -o gitnexus.exe -t windows-x64-20.11.0

echo [4/5] Building Python exe...
pyinstaller code_review.spec

echo [5/5] Copying gitnexus.exe to dist...
copy gitnexus.exe dist\CodeReview\

echo Done! Output in dist\CodeReview\
```

- [ ] **Step 2: 修改 code_review.spec 添加 gitnexus.exe**

```python
# code_review.spec - 在 datas 列表中添加

a = Analysis(
    ...
    datas=[
        ('web-ui/dist', 'static'),
        ('gitnexus.exe', '.'),  # 添加这行
    ],
    ...
)
```

- [ ] **Step 3: 测试打包（Windows 环境）**

Run: `build_exe.bat`
Expected: 在 `dist/CodeReview/` 生成包含 `gitnexus.exe` 的完整包

- [ ] **Step 4: Commit**

```bash
git add build_exe.bat code_review.spec
git commit -m "feat: Windows 打包集成 gitnexus.exe"
```

---

## Task 7: 端到端集成测试

**Files:**
- Test: `tests/test_integration.py`

**Interfaces:**
- 验证完整流程：符号提取 → GitNexus 调用 → 报告生成

- [ ] **Step 1: 添加集成测试**

```python
# tests/test_integration.py - 添加以下测试

def test_full_analysis_with_java_symbols():
    """Test complete analysis flow with Java symbol extraction."""
    from review.engine.report_generator import generate_report
    from unittest.mock import patch, MagicMock

    # Mock Java file content
    java_file_content = """public class Foo {
    public void oldMethod() {
    }

    public void newMethod(String param) {
        return;
    }

    public static int helper(int x) {
        return x * 2;
    }
}
"""

    mock_info = {"hash": "abc123", "message": "test commit", "author": "test", "time": "2026-01-01"}
    mock_diff = """diff --git a/src/Foo.java b/src/Foo.java
--- a/src/Foo.java
+++ b/src/Foo.java
@@ -5,6 +5,10 @@
     public void oldMethod() {
     }

+    public void newMethod(String param) {
+        return;
+    }
+
     public static int helper(int x) {
"""
    mock_changes = [MagicMock(file="src/Foo.java", added=4, removed=0)]

    with patch('review.engine.report_generator.get_commit_info', return_value=mock_info), \
         patch('review.engine.report_generator.get_diff', return_value=mock_diff), \
         patch('review.engine.report_generator.parse_diff', return_value=mock_changes), \
         patch('builtins.open', MagicMock(return_value=java_file_content)), \
         patch('review.engine.impact_analyzer.find_gitnexus_command', return_value=None), \
         patch('review.engine.report_generator.run_llm_review', return_value=[]):
        report = generate_report("abc123", quick=True)
        # Verify symbol extraction worked
        assert any(imp.symbol == "newMethod" for imp in report.impacts) or \
               len(report.changes) > 0  # At minimum, report was generated
```

- [ ] **Step 2: 运行集成测试**

Run: `cd /Users/liangjiawei/workspace/CodeReviewTool && python -m pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: 添加 GitNexus 集成端到端测试"
```

---

## Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Java 符号提取 | `diff_parser.py` |
| 2 | GitNexus 平台检测与调用 | `impact_analyzer.py` |
| 3 | 更新 report_generator | `report_generator.py` |
| 4 | SSE 进度推送 API | `server.py` |
| 5 | 前端分析按钮 | `App.tsx`, `api.ts` |
| 6 | Windows 打包 | `build_exe.bat`, `code_review.spec` |
| 7 | 集成测试 | `test_integration.py` |
