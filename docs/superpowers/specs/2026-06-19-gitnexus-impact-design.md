# GitNexus 影响分析集成设计

## 背景

当前 `diff_parser.py` 的 `get_changed_symbols` 只提取文件名 stem（如 `impact_analyzer.py` → `impact_analyzer`），而不是实际修改的函数/类名。GitNexus 的 `impact` 命令需要真正的符号名才能做影响分析，导致目前 GitNexus 基本没有在做有意义的分析。

## 目标

1. 从 diff 中提取实际修改的 Java 方法/类名
2. 调用 GitNexus 做符号级影响分析
3. 打包 GitNexus 到 Windows exe，Ubuntu 用 npx 自动下载
4. 在 Web UI Timeline 页面加「分析」按钮，点击后有进度反馈

## 环境约束

- **Ubuntu**：有 Node.js，能源码编译，但无法全局安装 gitnexus
- **Windows**：无任何依赖，需要打包成可用的 exe

## 设计

### 1. Java 符号提取

修改 `review/engine/diff_parser.py` 的 `get_changed_symbols`：

**输入**：`DiffChange` 列表（包含文件路径和 diff 内容）
**输出**：符号名列表（如 `["doSomething", "Foo", "helper"]`

**提取规则**：
- 类声明：`public class Foo` → `Foo`
- 方法声明：`public void doSomething(` → `doSomething`
- 构造函数：`public Foo(` → `Foo`
- 静态方法：`static int helper(` → `helper`

**实现方式**：
1. 对每个修改文件，读取当前版本文件内容
2. 用正则匹配所有方法/类签名，构建「符号 → 行号范围」映射
3. 解析 diff 的 `+` 行，确定哪些行被修改
4. 交叉匹配：如果某行在某个符号的行号范围内，该符号被修改
5. 返回去重后的符号列表

**正则模式**（Java）：
```python
# 类声明
r'(?:public|protected|private)?\s*(?:abstract|final|static)?\s*class\s+(\w+)'

# 方法/构造函数声明
r'(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?[\w<>\[\]]+\s+(\w+)\s*\('
```

### 2. GitNexus 调用层

修改 `review/engine/impact_analyzer.py`：

**GitNexus 发现顺序**：
1. Windows：检查工具目录下 `gitnexus.exe`（打包版）
2. Ubuntu/macOS：尝试 `npx gitnexus`（临时下载，不需全局安装）
3. 兜底：检查 PATH 中的 `gitnexus` 命令

**索引管理**：
- 调用 `gitnexus analyze <repo>` 建索引（首次需要几分钟）
- 索引存储在 `~/.review/gitnexus/<repo-name>/` 目录
- 检查索引是否存在，不存在自动触发 analyze
- 支持手动触发重新索引（UI 按钮）

**影响分析调用**：
```bash
gitnexus impact <symbol> --direction upstream --repo <repo_path> --file-path <file>
```

**输出解析**：
- 保持现有 `_parse_gitnexus_output` 逻辑
- 解析风险等级、受影响符号、受影响进程

### 3. Web UI 交互

修改 `web-ui/` 前端和 `review/web/server.py` 后端：

**Timeline 页面新增**：
- 在 commit 列表旁加「分析」按钮
- 点击后显示进度条和状态文字

**进度反馈**（使用 SSE）：
| 阶段 | 状态文字 |
|------|----------|
| 索引不存在 | "正在建立代码索引...（首次较慢）" |
| 索引更新中 | "正在更新索引..." |
| 影响分析 | "正在分析变更影响..." |
| LLM 审查 | "正在进行 AI 审查..." |
| 完成 | "分析完成" |

**后端 API**：
```
GET /api/analyze?commit=<hash>&repo=<path>&force=<bool>
  → SSE 流，推送进度事件
```

**事件格式**：
```
event: progress
data: {"stage": "indexing", "message": "正在建立代码索引..."}

event: progress
data: {"stage": "analyzing", "message": "正在分析变更影响..."}

event: done
data: {"report": {...}}
```

### 4. Windows 打包

修改 `build_exe.bat`：

**步骤**：
1. `npm install gitnexus` 安装 gitnexus 到本地 `node_modules`
2. 用 `nexe` 打包成独立 exe：
   ```bash
   npx nexe node_modules/gitnexus -o gitnexus.exe -t windows-x64-20.11.0
   ```
3. PyInstaller 打包时带上 `gitnexus.exe`：
   ```python
   # code_review.spec
   datas=[('gitnexus.exe', '.')]
   ```

**文件结构**（Windows exe 解压后）：
```
CodeReview/
├── CodeReview.exe          # 主程序
├── gitnexus.exe            # GitNexus CLI
└── web-ui/                 # 前端静态文件
```

## 改动文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `review/engine/diff_parser.py` | 重写 | `get_changed_symbols` 正则提取 Java 符号 |
| `review/engine/impact_analyzer.py` | 重构 | 平台检测 + nexe exe 发现 + 索引管理 |
| `review/web/server.py` | 新增 | SSE 进度推送 API |
| `web-ui/src/` | 新增 | Timeline 分析按钮 + 进度条组件 |
| `build_exe.bat` | 修改 | 添加 nexe 打包步骤 |
| `code_review.spec` | 修改 | 添加 gitnexus.exe 到 datas |
| `pyproject.toml` | 修改 | 添加 nexe 构建文档或脚本 |

## 验收标准

1. Ubuntu：`npx gitnexus impact <symbol>` 能返回影响分析结果
2. Windows：打包后的 exe 自带 gitnexus.exe，无需额外安装
3. 符号提取：从 Java diff 中正确提取方法/类名
4. Web UI：Timeline 页面点击「分析」按钮有进度反馈
5. 缓存：首次分析建立索引后，后续分析更快
