---
name: token-stats
description: "每次任务完成后精确汇报 token 消耗和大模型调用次数。跨平台支持 Hermes/Claude Code/OpenClaw/CodeX，含多模型场景的按模型分块表格统计"
version: 1.0.0
author: zhouhaoyong
license: MIT
source: https://github.com/zhouhaoyong/token-stats
tags:
  - token
  - usage
  - statistics
  - cross-platform
  - hermse
  - claude-code
  - codex
  - openclaw
---

# token-stats — 跨平台 Token 消耗统计

## 核心原则

1. **绝对不编造数字** — 所有数据来自 API 服务商返回的 `usage` 对象，经 Agent 框架写入本地存储
2. **任务开始保存基线** — 每次用户发新指令，`--save-baseline` 记录当前状态
3. **任务完成必报** — 结束后 `--delta` 输出本次增量/会话累计
4. **按占用比例给出建议** — < 60% 继续，60-89% 建议压缩，≥ 90% 建议 /new

## 前置条件

- Python 3.10+
- 至少一种 Agent 框架有使用记录：Hermes / Claude Code / OpenClaw / CodeX
- 安装方式：`pip install token-stats` 或直接下载 `token-stats.py`

## 安装

```bash
# 方式一：pip 安装（推荐）
pip install token-stats

# 方式二：手动下载
curl -O https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py
chmod +x token-stats.py
./token-stats.py --help
```

## 数据源

### 各后端数据位置

| 后端 | 数据源 | 数据可信度 |
|------|--------|-----------|
| Hermes | `~/.hermes/state.db` → sessions 表 | API 返回的 usage，经 `normalize_usage()` 处理后写入 |
| Claude Code | `~/.claude/projects/<hash>/<id>.jsonl` | 每条 assistant message 的 usage 字段 |
| OpenClaw | OpenClaw 数据目录下的 `sessions.json` | 会话级 + 消息级 + 轨迹级三级存储 |
| CodeX | `~/.codex/state_*.sqlite` → threads 表 | tokens_used 字段 |

### 数据字段说明

| 字段 | 含义 | 来源 |
|------|------|------|
| `input_tokens` | prompt tokens（不含缓存） | API 返回 |
| `output_tokens` | completion tokens | API 返回 |
| `cache_read_tokens` | 缓存命中读取 | API 返回 |
| `cache_write_tokens` | 缓存写入 | API 返回 |
| `reasoning_tokens` | 推理 tokens | API 返回 |
| `api_call_count` | LLM API 调用次数 | 框架自动计数 |
| `tool_call_count` | 工具调用次数 | 框架自动计数 |

## 统计工具用法

```bash
# 【任务开始时】记录基线
token-stats --save-baseline

# 【任务结束时】输出表格统计
token-stats --delta

# 查看当前累计占用
token-stats --summary

# 自动检测后端
token-stats --list-backends

# 数据完整性验证
token-stats --validate

# 手动指定后端
token-stats --save-baseline --backend claude-code
token-stats --delta --backend claude-code
```

## 任务流程

```
用户发新指令
    ↓
[--save-baseline]  ← 记录基线
    ↓
AI Agent 执行任务（多轮回复 + 多模型 + 多次工具调用）
    ↓
任务完成
    ↓
[--delta]          ← 输出表格统计
```

## 任务完成时的输出格式

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

### 格式说明

| 部分 | 含义 |
|------|------|
| **模型列** | 每个模型一行。多模型任务分块展示 |
| **调用次数 X/Y** | X = 本次任务增量，Y = 会话累计 |
| **输入/输出 tokens X/Y** | 同上 |
| **占用** | 基于模型上下文窗口的使用率。>100% 表示跨会话累计 |
| **⬇subagent** | 子代理（如 Claude Code Explore）的调用和消耗 |
| **底部 🗂** | 本次任务汇总 |
| **底部 📦** | 会话累计上下文占用 |

### 阈值建议

| 占用比例 | 输出 |
|----------|------|
| < 60% | ✅ 正常 |
| 60% ~ 89% | ⚠️ 建议压缩或 /trim |
| ≥ 90% | 🚨 建议立即 /new |
| > 100% | 跨会话累计，正常现象 |

## 模型上下文窗口自动检测

内置 `MODEL_CONTEXT_MAP`，当前覆盖约 30 个主流模型。未匹配的模型 fallback 到 128K。用户可自行扩展。

## 错误处理

| 问题 | 输出 |
|------|------|
| 数据库不存在 | ❌ Hermes 数据库不存在: path |
| 无会话记录 | ❌ 没有找到任何会话记录 |
| 未保存基线 | ❌ 未找到基线文件，请先运行 --save-baseline |
| 会话中途变更 | ❌ 会话已变更，需重新 --save-baseline |
| 数据异常（delta 为负） | ❌ 数据异常，请重新 --save-baseline |
| 无可用后端 | ❌ 未检测到任何受支持的 Agent 工具 |

## 关系文档

- `README.md` / `README.zh.md` — 完整使用文档（中英文）
- `docs/FAQ.md` — 常见问题
- `token-stats.py` — 主程序（单文件，零依赖）

## 注意事项

1. 每次任务开始必须调用 `--save-baseline`，结束调用 `--delta`
2. 格式 `X/Y`：X = 本次任务增量，Y = 会话累计（上下文占用除外）
3. Cache Read 通常远大于 input tokens（system prompt + 记忆 + 技能计入缓存）
4. Claude Code 的 JSONL 文件包含项目下所有会话的累计数据，所以累计值可能超过上下文窗口
5. 数据实时更新 — 每次 AI 回复后自动写入
6. 跨会话后基线失效，需重新 `--save-baseline`
