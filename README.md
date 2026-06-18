# Code Review Tool

代码审查工具 — 分析 Git 提交对已有代码的潜在影响。支持 GitNexus 符号级影响分析 + LLM 语义审查，终端 CLI + Web 双输出，支持一键 Windows 打包。

## 快速开始

### Windows 一键端

从 [Releases](https://github.com/LiangjwZZZZ/Code-Review-Tool/releases) 下载 `CodeReview-Windows.zip`，解压后双击 `CodeReview.exe` 即可使用。

首次启动会自动打开浏览器，进入设置页面配置 API Key 和仓库路径。

### 从源码安装

**依赖：**
- Python 3.12+
- Node.js 20+ 和 npm
- GitNexus v1.6.4+（可选，用于符号级影响分析）

```bash
cd CodeReviewTool
pip install -e .
cd web-ui && npm install && npm run build && cd ..
```

## 使用方式

### Web 界面（推荐）

```bash
# 启动服务
python -c "from review.web.server import start_server; start_server()"

# 或直接用 launcher
python -m review
```

访问 http://localhost:9090

**基本工作流：**

1. **设置** → 配置 API Key（DeepSeek / Anthropic）+ 仓库路径
2. **时间线** → 选择仓库和分支 → 浏览 commit 列表
3. 点击 commit → 预览 diff → 点击「分析」运行完整审查
4. 查看报告：风险概览 → LLM 审查 → 影响图 → 逐文件详情

**逐文件分析：** 在 Changed Files 中点击文件展开 diff，再点「分析这段改动」按需触发 LLM 审查。

### CLI

```bash
# 分析提交
review check <commit-hash> --repo /path/to/repo
review check --quick <commit-hash>        # 跳过 LLM

# 查看报告列表
review history
```

### 仓库路径配置

- **普通 Git 仓库：** 直接填仓库根目录路径（如 `/home/user/project` 或 `D:\code\my-project`）
- **Android Repo 项目：** 填 repo 工具的根目录（包含 `.repo/manifest.xml`），自动检测所有子仓库，左侧树形侧边栏切换
- **Windows Cygwin 用户：** 填 Windows 原生路径（如 `E:\WorkSpace\Code\WB\WB-8678`），工具会自动处理路径格式

## 功能特性

| 功能 | 说明 |
|------|------|
| LLM 语义审查 | DeepSeek / Anthropic API，自动分析 breaking change、安全、架构、质量问题 |
| 符号级影响分析 | GitNexus 集成，追踪函数/类的上下游调用链 |
| 影响图 | 可视化展示变更影响范围，按 module 着色 |
| 跨 Module 分析 | 自动解析 `settings.gradle`，高亮跨模块调用 |
| Gerrit 集成 | 输入 Gerrit URL 自动 fetch + 分析，支持 HTTP 认证 |
| 多仓库管理 | Android Repo 自动检测，全局/单仓库分支切换 |
| 逐文件审查 | 按文件粒度触发 LLM 分析，避免全量审查的 token 浪费 |
| 崩溃日志 | 未捕获异常写入 `~/.review/logs/crash.log`，方便排查 |

## 配置

Web 模式下在 `/settings` 页面配置，持久化到 `~/.review/config.json`：

| 配置项 | 说明 |
|--------|------|
| API 类型 / Key / 模型 | DeepSeek 或 Anthropic |
| 仓库路径 | Git 仓库根目录或 Android Repo 根目录 |
| Git 路径 | 留空用系统默认，或指定完整路径（如 `D:\cygwin\bin\git.exe`） |
| 日志目录 | 默认 `~/.review/logs/` |
| Gerrit 认证 | Gerrit 用户名 + HTTP 密码（Settings → HTTP Credentials） |

## 开发

```bash
# 后端
pip install -e .

# 前端
cd web-ui && npm install && npm run dev

# 构建 Windows exe
build_exe.bat
```

## 技术栈

- **后端：** Python / FastAPI / uvicorn
- **前端：** React / TypeScript / Vite
- **打包：** PyInstaller（Windows exe）
- **分析：** GitNexus + DeepSeek / Anthropic LLM
