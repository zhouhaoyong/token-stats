<p align="center">
  <a href="README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="README.zh.md"><strong>🇨🇳 简体中文</strong></a>
</p>

# token-stats

> 🎯 跨平台 AI 编码助手 token 消耗精确统计工具。

`token-stats` 是一个 CLI 工具，精确统计 **每次任务的 token 和 LLM 调用次数**。支持 **4 大主流 Agent 框架**，统一命令操作。

## ✨ 特性

- **按任务统计**：不是累计值，只算本次任务消耗了多少
- **多模型感知**：支持在任务中切换不同模型，按模型分块展示
- **子代理检测**：自动识别 Claude Code Explore、OpenClaw 子任务等
- **跨平台**：macOS / Linux / Windows 全兼容（纯 Python + SQLite + JSON）
- **支持的 Agent**：

| 后端 | 数据源 | 粒度 |
|------|--------|------|
| Hermes Agent | `~/.hermes/state.db` (SQLite) | 会话级累计 |
| Claude Code | `~/.claude/projects/**/*.jsonl` | 每条消息 + 子代理 |
| OpenClaw | OpenClaw 会话数据 (JSON) | 会话级 + 轨迹追踪 |
| CodeX | `~/.codex/state_*.sqlite` | 线程级累计 |

- **自动检测**：无需配置，直接运行
- **表格输出**：按模型分块展示，带上下文窗口占比警告

---

## 🚀 按操作系统安装

请根据你的操作系统选择下方对应章节，包含各 Agent 的详细用法。

---

### 🍎 macOS

**默认 shell：** zsh（macOS Catalina 起）

#### 第 1 步 — 安装 token-stats

```bash
# 方式一：ClawHub 安装（OpenClaw 用户推荐）
clawhub install agent-usage-stats

# 方式二：直接下载（零依赖，通用）
curl -O https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py
chmod +x token-stats.py
```

#### 第 2 步 — 配置命令别名

```bash
# 添加到 ~/.zshrc
echo 'alias token-stats="python3 ~/.hermes/skills/agent-usage-stats/token-stats.py"' >> ~/.zshrc
source ~/.zshrc

# (如果直接下载的脚本，请使用实际路径)
```

验证是否成功：
```bash
token-stats --list-backends
```

#### 第 3 步 — 配合各 Agent 使用

**配合 Hermes Agent：**

```bash
# token-stats 在 Hermes 中已作为 skill 集成。
# 在 Hermes 聊天中，每次新任务开始时：
token-stats --save-baseline

# 正常使用 Hermes 干活...

# 任务结束时统计消耗：
token-stats --delta
```

**配合 Claude Code：**

```bash
# 先在终端中保存基线：
token-stats --save-baseline --backend claude-code

# 然后启动 Claude Code 工作：
claude

# 退出 Claude Code 后查看消耗：
token-stats --delta --backend claude-code
```

**配合 OpenClaw：**

```bash
token-stats --save-baseline --backend openclaw
# 使用 OpenClaw...
token-stats --delta --backend openclaw
```

**配合 CodeX：**

```bash
token-stats --save-baseline --backend codex
# 使用 CodeX...
token-stats --delta --backend codex
```

---

### 🐧 Linux

**默认 shell：** bash

#### 第 1 步 — 安装 token-stats

```bash
# 方式一：ClawHub
clawhub install agent-usage-stats

# 方式二：直接下载
curl -O https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py
chmod +x token-stats.py
```

#### 第 2 步 — 配置命令别名

```bash
# 添加到 ~/.bashrc
echo 'alias token-stats="python3 ~/.hermes/skills/agent-usage-stats/token-stats.py"' >> ~/.bashrc
source ~/.bashrc
```

#### 第 3 步 — 配合各 Agent 使用

各 Agent 的使用命令与 macOS 完全一致，见上方 macOS 章节：

```bash
# Hermes Agent
token-stats --save-baseline    # 任务前
token-stats --delta            # 任务后

# Claude Code
token-stats --save-baseline --backend claude-code
claude
token-stats --delta --backend claude-code

# OpenClaw / CodeX — 同样模式，换后端参数即可
```

---

### 🪟 Windows

**默认 shell：** PowerShell

#### 第 1 步 — 安装 token-stats

```powershell
# 方式一：ClawHub（需要 Node.js）
clawhub install agent-usage-stats

# 方式二：直接下载（PowerShell）
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py" -OutFile "token-stats.py"
```

#### 第 2 步 — 配置命令

```powershell
# 添加到 PowerShell 配置文件
echo "`nfunction token-stats { python3 `"$HOME\.hermes\skills\agent-usage-stats\token-stats.py`" @args }" >> $PROFILE

# 或重新加载配置
. $PROFILE
```

#### 第 3 步 — 配合各 Agent 使用

**配合 Hermes Agent：**

```powershell
token-stats --save-baseline
# 在 QQ/Telegram/终端中使用 Hermes...
token-stats --delta
```

**配合 Claude Code：**

```powershell
token-stats --save-baseline --backend claude-code
claude
token-stats --delta --backend claude-code
```

**配合 CodeX：**

```powershell
token-stats --save-baseline --backend codex
# 使用 CodeX...
token-stats --delta --backend codex
```

> **注意：** OpenClaw 后端在 Windows 上支持有限（需自定义路径）。

---

## 🔧 基础用法

### 自动检测模式

```bash
# 列出检测到的后端
token-stats --list-backends

# 验证数据完整性
token-stats --validate

# 查看当前累计占用
token-stats --summary
```

---

## 📊 输出示例

```
┌──────────────────┬───────────────────┬───────────────────┬──────────────────┬───────────┐
│      模型        │      调用次数      │     输入 tokens    │    输出 tokens   │   占用    │
├──────────────────┼───────────────────┼───────────────────┼──────────────────┼───────────┤
│ deepseek-v4-pro  │       2/1,715   │    12,340/1.4M   │     5,678/816K  │  >100%  │
│ claude-sonnet-4  │       1/5       │     8,234/29K    │     3,456/12K   │  14.5%✅│
│ ⬇subagent        │       3/12      │     2,100/48K    │     1,200/28K   │  58.4%✅│
└──────────────────┴───────────────────┴───────────────────┴──────────────────┴───────────┘
 🗂  claude-code · 3/1720 次调用 · 34,009 tokens · 子代理: 3/12
 📦  累计: 2,355K/1,048,576 tokens (>100%)
```

**每行的 X/Y 格式说明：**

| 部分 | 含义 |
|------|------|
| **X**（左边） | **本次任务** — 自 `--save-baseline` 以来的消耗 |
| **Y**（右边） | **会话累计** — 数据文件中的全部累计值 |
| **占用 %** | 上下文窗口使用率（基于模型自动检测） |

---

## ⚙️ 工作原理

```
用户开始任务 → token-stats --save-baseline (记录快照)
    ↓
用户使用 AI 编码助手（任意模型、任意轮次）
    ↓
任务完成 → token-stats --delta (对比快照，输出差值)
    ↓
表格展示：每个模型的调用次数、token 消耗、上下文占用
```

工具在任务开始时保存 Agent 数据的"基线快照"。任务结束时对比当前数据和基线，只输出**差值**——即本次任务的真实消耗。所有数据均来自 API 服务商返回的 `usage` 对象，由 Agent 框架自动记录。

---

## 🔍 数据完整性验证

```bash
# 验证 Agent 数据是否完整、可信
token-stats --validate
```

校验项目：
- 数据库/文件是否存在
- Token 数据是否合理（非负、有 API 调用时 token 不应为 0）
- 所有必要字段是否已填充

---

## 🐛 支持的模型（上下文窗口自动检测）

| 系列 | 模型 | 窗口 |
|------|------|------|
| DeepSeek | v4-flash, v4, chat, reasoner | 1,048,576 (1M) |
| OpenAI | GPT-4o, GPT-4o-mini, o1, o3, o4-mini | 128K ~ 1M |
| Anthropic | Claude Sonnet/Opus/Haiku 3/4 | 204,800 (200K) |
| Google | Gemini 2.5 Pro, 2.0 Flash, 1.5 Pro | 1M ~ 2M |
| Qwen | Qwen3, 3.6, Max, Plus, Turbo | 128K ~ 1M |
| 其他 | Llama 3.1, Mistral Large, Mixtral | 8K ~ 128K |

未匹配的模型默认 128K。模型映射表可扩展，欢迎 PR！

---

## 📦 作为 Hermes Agent Skill 使用

```bash
# 通过 ClawHub 安装：
clawhub install agent-usage-stats

# 在 Hermes 中直接使用：
token-stats --save-baseline   # 任务开始
token-stats --delta            # 任务结束
```

本仓库中的 `SKILL.md` 提供了完整的 Hermes 集成配置，支持任务后自动输出统计。

---

## 🔧 环境要求

- Python 3.10+
- 无需外部依赖（仅使用标准库：`sqlite3`, `json`, `os` 等）
- 至少安装一种 Agent：Hermes Agent / Claude Code / OpenClaw / CodeX

---

## 📄 开源协议

MIT

---

## 🤝 贡献指南

欢迎 PR！特别是：
- 添加新的模型上下文窗口
- 新的后端适配器
- 多语言翻译
- Bug 反馈
