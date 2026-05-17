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

## 🚀 快速开始

```bash
# 1. 安装
pip install token-stats
# 或者直接下载 token-stats.py — 单个文件即可运行！

# 2. 开始任务前记录基线
token-stats --save-baseline

# 3. 正常使用你的 AI 编码助手（任意模型、任意轮次）

# 4. 查看本次任务消耗了多少 token
token-stats --delta
```

### 自动检测模式

`token-stats` 自动检测你正在使用的 Agent 框架：

```bash
# 列出检测到的后端
token-stats --list-backends

# 验证数据完整性
token-stats --validate

# 查看当前累计占用
token-stats --summary
```

### 手动指定后端

```bash
# Claude Code
token-stats --save-baseline --backend claude-code
token-stats --delta --backend claude-code

# OpenClaw
token-stats --save-baseline --backend openclaw
token-stats --delta --backend openclaw

# CodeX
token-stats --save-baseline --backend codex
token-stats --delta --backend codex
```

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

## 🔍 数据完整性验证

```bash
# 验证 Agent 数据是否完整、可信
token-stats --validate
```

校验项目：
- 数据库/文件是否存在
- Token 数据是否合理（非负、有 API 调用时 token 不应为 0）
- 所有必要字段是否已填充

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

## 📦 作为 Hermes Agent Skill 使用

`token-stats` 也可作为 [Hermes Agent](https://github.com/nousresearch/hermes-agent) 的 skill 安装：

```bash
# 在 Hermes 中直接使用：
token-stats --save-baseline   # 任务开始
token-stats --delta            # 任务结束
```

本仓库中的 `SKILL.md` 提供了完整的 Hermes 集成配置，支持任务后自动输出统计。

## 🔧 环境要求

- Python 3.10+
- 无需外部依赖（仅使用标准库：`sqlite3`, `json`, `os` 等）
- 至少安装一种 Agent：Hermes Agent / Claude Code / OpenClaw / CodeX

## 📄 开源协议

MIT

## 🤝 贡献指南

欢迎 PR！特别是：
- 添加新的模型上下文窗口
- 新的后端适配器
- 多语言翻译
- Bug 反馈
