# Review Tool

代码审查工具 — 输入 commit hash，分析代码变更对已有代码的潜在影响。支持 GitNexus 符号级影响分析 + LLM 语义审查，终端 CLI + Web 双输出。

## 功能

- **影响分析** — 基于 GitNexus 分析变更符号的调用链影响范围
- **LLM 审查** — 自动生成代码审查意见（支持 DeepSeek / Anthropic）
- **Web 界面** — 时间线浏览、分支切换、分析报告查看
- **桌面启动器** — tkinter 原生窗口，一键安装依赖 + 启动服务
- **日志持久化** — 所有操作日志写入本地文件

## 快速开始

### 前置要求

- Python 3.8+
- Node.js 16+ 和 npm
- Git

### 环境变量

```bash
export DEEPSEEK_API_KEY=sk-xxxxxx
# 或
export ANTHROPIC_API_KEY=sk-ant-xxxxxx
```

### 方式一：桌面启动器（推荐）

```bash
# 进入项目目录
cd review-tool

# 直接运行启动器（会自动安装 Python 依赖）
python review/launcher.py
```

在弹出的窗口中：
1. 配置 API Key、模型等参数
2. 填写仓库路径（要分析的 Git 仓库目录）
3. 点击 **⚡ 一键启动**
4. 启动完成后自动打开浏览器，访问 Web 界面

启动器会自动完成：
- `pip install -e .`（安装 Python 依赖）
- `npm install && npm run build`（构建前端）
- 启动后台服务

### 方式二：手动启动

```bash
# 1. 安装 Python 依赖
pip install -e .

# 2. 安装并构建前端
cd web-ui
npm install
npm run build
cd ..

# 3. 启动服务
python -c "from review.web.server import start_server; start_server()"

# 4. 打开浏览器访问
# http://127.0.0.1:9090/timeline
```

## 使用指南

### Web 界面

1. 打开 `http://127.0.0.1:9090/timeline`
2. 选择分支，点击 commit 进行分析
3. 分析完成后查看报告：
   - **概览卡片** — 风险等级、变更统计
   - **影响图** — 符号影响关系
   - **审查详情** — LLM 生成的代码审查意见
   - **社区聚类图** — 影响模块聚类
4. 在报告页可以**重新分析**，选择模式：
   - 默认 — 包含 LLM 分析
   - 快速 — 仅影响分析，跳过 LLM

### 配置说明

Web 模式下可在 `/settings` 页面配置（持久化保存到 `~/.review/config.json`）：

| 配置项 | 说明 |
|--------|------|
| API 类型 | deepseek 或 anthropic |
| API Key | LLM 调用的 API 密钥 |
| 模型 | 模型名称（如 deepseek-v4-flash） |
| Host | 服务监听地址 |
| 端口 | 服务监听端口 |
| 仓库路径 | 要分析的 Git 仓库路径 |
| 日志目录 | 日志文件存储位置（默认 ~/.review/logs/） |

CLI 模式通过环境变量配置：

| 环境变量 | 说明 |
|----------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API key（默认） |
| `DEEPSEEK_MODEL` | DeepSeek 模型名（可选，默认 deepseek-v4-flash） |
| `ANTHROPIC_API_KEY` | Anthropic API key（与 DeepSeek 二选一） |

### CLI 使用

CLI 需要先设置环境变量配置 API key：

```bash
# DeepSeek（默认）
export DEEPSEEK_API_KEY=sk-xxxxxx
export DEEPSEEK_MODEL=deepseek-v4-flash  # 可选，默认 deepseek-v4-flash

# 或 Anthropic
export ANTHROPIC_API_KEY=sk-ant-xxxxxx
```

命令参考：

```bash
# 查看帮助
review --help

# 分析一个 commit
review analyze <commit-hash> --repo /path/to/repo

# 快速模式（跳过 LLM）
review analyze <commit-hash> --quick

# 列出已生成的分析报告
review list

# 查看报告
review show <commit-hash>
```

> Web 模式无需设置环境变量，API key 在 `/settings` 页面配置后持久化保存。

## 项目结构

```
review/
├── review/
│   ├── engine/
│   │   ├── diff_parser.py      # Git diff 解析
│   │   ├── impact_analyzer.py  # GitNexus 影响分析
│   │   ├── llm_reviewer.py     # LLM 审查
│   │   └── report_generator.py # 报告生成
│   ├── store/
│   │   └── report_store.py     # SQLite 存储
│   ├── web/
│   │   └── server.py           # FastAPI Web 服务
│   ├── cli.py                  # Typer CLI
│   ├── config.py               # 配置管理
│   ├── launcher.py             # tkinter 桌面启动器
│   └── models.py               # 数据模型
├── web-ui/
│   └── src/                    # React 前端
│       ├── api.ts              # API 调用
│       ├── components/         # 组件
│       └── pages/              # 页面
├── pyproject.toml
└── README.md
```

## Windows 注意事项

1. **Python** — 从 python.org 下载安装，安装时勾选 "Add Python to PATH"
2. **Node.js** — 从 nodejs.org 下载安装
3. **Git** — 从 git-scm.com 下载安装
4. **tkinter** — Windows 版 Python 自带，无需额外安装
5. **路径** — 仓库路径用绝对路径或相对路径均可，Windows 上用反斜杠或正斜杠都行
6. **启动器** — 双击 `review/launcher.py` 或在终端运行 `python review/launcher.py`
7. **如果启动器窗口中文乱码** — 在终端先运行 `chcp 65001` 切换 UTF-8

## 日志

日志存储在配置的日志目录中（默认 `~/.review/logs/`）：

- `launcher.log` — 启动器操作日志
- `server-YYYY-MM-DD.log` — 服务端运行日志（包含所有 HTTP 请求和分析事件）

## 关闭服务

- Web 界面：`/settings` 页面点击「关闭服务」
- 桌面启动器：点击「关闭服务」按钮
- 或直接关闭启动器窗口（后台服务继续运行）
