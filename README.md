# Review Tool

代码审查工具 — 分析 Git 提交对已有代码的潜在影响。支持 GitNexus 符号级影响分析 + LLM 语义审查，终端 CLI + Web 双输出。

## 安装

### 依赖

- Python 3.12+
- Node.js 16+ 和 npm
- GitNexus v1.6.4+

### 步骤

```bash
# 安装 Review Tool
cd CodeReviewTool
pip install -e .
# 安装后 review 命令即可用
cd web-ui && npm install && npm run build && cd ..
```

### 环境变量（CLI 模式）

```bash
export DEEPSEEK_API_KEY=sk-xxxxxx
# 或
export ANTHROPIC_API_KEY=sk-ant-xxxxxx
```

Web 模式无需设置环境变量，API Key 在页面配置后持久化。

## 使用

### CLI

```bash
# 索引仓库（首次使用）
review index --repo /path/to/repo

# 分析提交
review check <commit-hash> --repo /path/to/repo
review check --quick <commit-hash>        # 跳过 LLM
review check --repo /path/to/repo <hash>  # 指定仓库

# 查看报告列表
review history

# 启动 Web
review web
```

### Web

```bash
python -c "from review.web.server import start_server; start_server()"
# 访问 http://localhost:9090/timeline
```

**工作流：**

```
1. /timeline → 选择仓库 → 选择分支 → 点击 commit
2. 预览 commit 信息 + changed files + diff（未分析时自动显示）
3. 点击"分析此提交"运行完整分析
4. 查看报告：风险概览 → LLM 审查 → 影响图 → 跨 Module 影响 → 逐文件浏览
```

**逐文件分析：** 在 Changed Files 中点击文件展开 diff + 影响链，再点"分析这段改动"按需触发 LLM 审查。

**多仓库切换（Android Repo）：** 设置页面填写 Android repo 根目录，自动解析 `.repo/manifest.xml` 检测所有子仓库。左侧树形侧边栏切换子仓库、全局切换分支。

**Gerrit 集成：** 时间线页面顶部输入 Gerrit 变更 URL（如 `https://gerrit.example.com/c/my-project/+/12345/3`），自动 fetch 对应 change 并运行完整分析，无需手动 checkout。

**Android 多 Module：** 自动解析 `settings.gradle`，影响图按 module 着色，跨 module 调用链高亮展示。

**报告页布局：**
```
概览卡片 → LLM 审查 → 影响图 → 跨 Module 影响卡片 → 逐文件面板
```

## 配置

Web 模式下在 `/settings` 页面配置，持久化到 `~/.review/config.json`：

| 配置项 | 说明 |
|--------|------|
| API 类型 / Key / 模型 | deepseek 或 anthropic |
| 仓库路径 | 默认 Git 仓库路径 |
| 日志目录 | 默认 ~/.review/logs/ |
