# review — 提交影响分析工具

分析某次提交（commit）对已有代码的潜在影响和破坏风险，输出终端摘要 + Web 可视化报告。

## 快速开始

```bash
# 先为仓库建立 GitNexus 索引（仅首次）
review index

# 检查某次提交
review check <commit-hash>

# 启动 Web 界面查看报告
review web
```

## 环境要求

- Python 3.12+
- GitNexus v1.6.4（需预先安装并索引目标仓库）
- ANTHROPIC_API_KEY（可选，无 key 时跳过 LLM 审查，只做影响分析）

## 命令参考

### `review check <commit>` — 检查提交

核心命令。分析指定提交的代码变更、影响范围和潜在风险。

| 选项 | 说明 |
| --------- | ------------------------------------------------------------- |
| `--quick` | 跳过 LLM 审查，只做 GitNexus 影响分析（速度更快） |
| `--repo`  | 指定仓库路径（默认当前目录） |

示例：

```bash
review check abc1234
review check --quick abc1234
review check --repo /path/to/repo abc1234
```

### `review diff <branch> [base]` — 分支间差异

对比两个分支之间的变更影响。`base` 默认 `main`。

```bash
review diff feature/login
review diff feature/login develop
```

### `review status` — 工作区变更

分析未提交的工作区变更。

```bash
review status
review status --quick
```

### `review web [commit]` — Web 可视化

启动 Web 服务，在浏览器中查看审查报告。

| 选项 | 说明 |
|------|------|
| `-p / --port` | 指定端口（默认 9090） |

```bash
review web                    # 查看所有报告列表
review web abc1234            # 直接打开指定报告
review web -p 8080            # 指定端口
```

Web 界面包含：
- **概览卡片** — 提交信息、风险等级（颜色标记）
- **文件变更列表** — 增删行数统计
- **影响关系图** — vis-network 交互式图谱，红色 = 高风险，蓝色 = 被影响
- **审查详情** — LLM 发现的潜在问题（如有 API Key）

### `review history` — 历史记录

列出最近的审查报告。

```bash
review history
```

### `review index` — 初始化索引

为目标仓库初始化 GitNexus 索引，`review check` 前需要先运行一次。

```bash
review index
review index --repo /path/to/repo
```

## 工作流程

```
1. review index         ← 首次使用，建立代码知识图谱索引
2. review check <hash>  ← 分析提交
3. review web           ← 查看可视化报告
   或 review web <hash> ← 直接打开特定报告
```

## 数据存储

报告存储在 `~/.review/reports.db`（SQLite），无需额外配置。

## 风险等级说明

| 等级 | 颜色 | 含义 |
|------|------|------|
| CRITICAL | 红色 | 破坏性变更，影响面广 |
| HIGH | 橙色 | 高风险，可能引发下游错误 |
| MEDIUM | 黄色 | 中等风险，建议关注 |
| LOW | 绿色 | 低风险，安全变更 |

## 常见问题

**Q: 提示 "gitnexus: command not found"**
A: 需要先安装 GitNexus v1.6.4+。

**Q: 报告显示 "No findings"**
A: `--quick` 模式会跳过 LLM 审查；或者未设置 `ANTHROPIC_API_KEY` 环境变量时会自动降级。

**Q: Web 页面显示空白**
A: 确认前端已构建（`web-ui/` 目录下运行 `npm run build`），输出在 `review/web/static/`。
