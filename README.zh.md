# token-stats — 选个 Agent 看它的消耗

每次运行都让你选，想看哪个 Agent 就看哪个。

## 一句话说明

你的电脑上装了多个 AI 助手（Hermes、Claude Code、CodeX、OpenClaw……），
`token-stats` 可以告诉你**每个助手到底用掉了多少 tokens**。

> ⚠️ **重要说明：本工具仅统计本机的 Agent 数据。**
> 如果你在不同 PC 或服务器上运行 Agent，各自的数据仅保存在各台机器上，
> 无法跨机器统计。每台机器需要各自安装本工具查看。
> 
> 所有统计都是基于你选择的某个 Agent 来查询的，不是特指某一个。

---

## 为什么选择 token-stats

`token-stats` 直接读取本地数据，跨 Agent、跨模型、跨平台运行。零依赖，纯 Python 标准库。

| 功能 | 命令 | 说明 |
|------|------|------|
| **Token 消耗统计** — 指定时间范围 | `token-stats -b hermes --today` | 多 Agent（Hermes / Claude Code / CodeX / OpenClaw）、多模型，输入/输出/缓存 token 和调用次数，有数据才展示 |
| **实时监控** — 上下文占比追踪 | `token-stats -b hermes --watch` | 每轮增量 + 累计量，超 90% 预警，macOS / Linux / Windows 通用 |
| **时段对比** — 两个时间段并排比较 | `--compare --a today --b yesterday` | 任意时间段聚合，多模型横向对比，带差值列 |
| **数据导出** — JSON / CSV | `--export` | 多 Agent、多时间段组合，交互式选目录 |
| **模型识别** — 中转站 API 校验 | `token-stats -b <name>` | 自动识别 API 返回的模型名称（69 个模型 13 个厂商） |

---

## 环境要求

装 `token-stats` 之前，你的电脑需要先有这些东西：

### 1. Python 3.8+

`token-stats` 本身是纯 Python 脚本，依赖标准库，不需要额外 pip 装任何包。

```bash
# 检查已安装（Windows 用户用 python --version）
python3 --version

# 如果没装 → 去 https://www.python.org/downloads/ 下载
```

### 2. Node.js（安装工具时需要）

`token-stats` 通过 **ClawHub CLI** 安装。ClawHub 是个 Node.js 命令行工具。

```bash
# 检查已安装
node --version

# 如果没装 → 去 https://nodejs.org 下载（选 LTS 版本）
```

装好 Node.js 后会自动带上 `npm`，用来装 ClawHub。

### 3. ClawHub CLI

```bash
# 安装（npm 全局安装）
npm install -g clawhub

# 验证
clawhub -V          # 显示版本号
```

> 💡 如果你用的是 macOS 且通过 Homebrew 装过 Node.js，
> `npm install -g clawhub` 安装后会出现在 `/opt/homebrew/bin/clawhub`，
> 通常已经在你 PATH 里了，直接用就行。

---

### 数据范围

> ⚠️ `token-stats` **仅统计本机数据，不跨机器汇总**。
>
> - **同一把 API Key 用在多台机器 → 每台机器的统计互不相通**
> - 例：API Key 同时在 PC A 和 PC B 用，PC A 的 `token-stats` 只看得到 PC A 的用量
> - `token-stats` 不联网、不查 API 后台，纯读本地磁盘文件
> - 要看另一台机器的统计，请在那台机器上也安装 `token-stats`

### API 中转站 / 代理服务

> 如果你通过 **API 中转站** 访问大模型，请注意以下限制。

token-stats 依赖 API 返回的 `usage` 对象来统计消耗。数据链路如下：

```
你的 Agent → 中转站 → 真实 API
                         ↓
           真实 API 返回 usage 对象
                         ↓
           中转站将响应转发给你的 Agent
                         ↓
           你的 Agent 写入本地存储
                         ↓
           token-stats 读取本地存储
```

**统计准确的条件：** 中转站将原始 API 响应 **原样透传**（含 `usage` 字段）。多数主流中转站都这样做。

**统计可能不准的条件：** 中转站：
- 移除了 `usage` 字段
- 篡改了 token 数量（如虚增用量）
- 替换了模型名称

token-stats **只记录收到的数据**，不校验数据是否与真实 API 一致。它是**本地账本**，记的是 Agent 记下的账，不是上游 API 的结算账单。

> 如果怀疑中转站数据不实，请将 token-stats 输出与中转站结算后台对比。不一致说明数据可能被修改过。

---

token-stats 本质上是一个**开源透明度工具**。它本身不评判中转站的好坏，而是让 token 消耗变得**可审计、可验证**：

- 对**诚实中转站**：用户能自行核对，反而建立信任
- 对**不诚实中转站**：数据差异会暴露问题

无论直连还是走中转，用户都应该有权知道自己的真实消耗。token-stats 不站队，只记账。

## 安装

满足以上环境后，两行命令搞定：

**macOS / Linux：**
```bash
cd ~
clawhub install agent-usage-stats
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

**Windows（PowerShell）：**
```powershell
cd ~
clawhub install agent-usage-stats
python $HOME\skills\agent-usage-stats\token-stats.py setup
```

> `cd ~` 确保技能安装到用户主目录（所有系统都有写入权限）。
> 如果 `python` 找不到，试试 `python3`（Microsoft Store 版 Python 用 `python3`）。
> 如果报错 `can't open file '...~...'`，参考：[PowerShell 路径展开问题](#ps-tilde)。
>
> `setup` 会自动将 `~/.local/bin` 加入系统 PATH，**需要新开一个终端窗口**才能生效。

好了。新开终端，直接敲 `token-stats` 就能用。

### 验证安装成功

```bash
# 验证 1：版本号
token-stats --version
# 输出: token-stats v2.3.3

# 验证 2：看本机已安装的 Agent
token-stats --list-backends
# 输出示例:
#   ✅ Hermes
#   ✅ Claude Code
#   ❌ CodeX
#   ❌ OpenClaw

# 验证 3：直接看某个 Agent 的统计
token-stats -b hermes
# 输出示例:
# 📊 Hermes
#   deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 调用 13 次
```

如果以上三条都正常输出，说明安装完全成功 🎉

## 更新

**macOS / Linux：**
```bash
clawhub update agent-usage-stats
python3 ~/skills/agent-usage-stats/token-stats.py setup
token-stats --version
```

**Windows（PowerShell）：**
```powershell
clawhub update agent-usage-stats
python $HOME\skills\agent-usage-stats\token-stats.py setup
token-stats --version
```

> 💡 每次更新后建议重新执行 `setup`。如果版本没变，加 `--force` 强制重装：
> ```
> clawhub install agent-usage-stats --force
> ```

---

## 常用命令

日常用得最多的几条，复制即用：

```bash
# 📊 查看本机所有 Agent 统计
token-stats --all

# 📊 查看今天所有 Agent 数据
token-stats --all --today

# 📊 查看本月所有 Agent 数据（例：2026年5月）
token-stats --all --from 2026-05-01 --to 2026-05-31

# 📤 要导出 → 加 --export（交互式选择目录和格式）
token-stats --all --export
token-stats --all --today --export
token-stats --all --from 2026-05-01 --to 2026-05-31 --export

# 🎯 指定单个 Agent
token-stats -b hermes
token-stats -b hermes --today
token-stats -b hermes --from 2026-05-01 --to 2026-05-31

# ⚖️ 今日 vs 昨日对比
token-stats -b hermes --compare --a today --b yesterday

# 👀 实时监控上下文（边聊边看，快满屏了会预警）
token-stats -b hermes --watch

# 👀 交互式选 Agent 后进入实时监控
token-stats --watch
```

> 把 `hermes` 换成你自己的 Agent 名字（`claude-code` / `codex` / `openclaw`）即可。

## 用法

### 快速查看

```bash
# 交互式选择
token-stats

# 直接指定 Agent（跳过菜单）
token-stats -b hermes
token-stats -b claude-code
token-stats -b codex
token-stats -b openclaw

# 同时查看多个 Agent（逗号分隔）
token-stats -b hermes,claude-code

# 查看本机所有 Agent
token-stats --all

# 当前快照（同默认）
token-stats -b hermes --now

# 详细模式（显示更多信息）
token-stats -b hermes --detail
```

所有命令都支持切换 Agent 名称，例如：
- `-b hermes` → Hermes
- `-b claude-code` → Claude Code
- `-b codex` → CodeX
- `-b openclaw` → OpenClaw

输出示例（每个模型一行，仅显示有数据的模型）：
```
📊 Hermes
  deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 缓存 480.6K | 调用 13 次 | 第 16 轮 "..."

📊 Claude Code
  deepseek-v4-pro | 上下文 2.60M/1.05M (>100%) | 输入 1.78M | 输出 823.0K | 缓存 341.48M | 调用 1723 次
  Qwen3-Coder-30B | 上下文 23.0K/131.1K (17.6% ✅) | 输入 22.9K | 输出 131 | 调用 1 次
```

### 时间段查询

查看某段时间内的总消耗（不显示上下文占比，显示会话数）：

```bash
# 今天（各 Agent 通用）
token-stats -b hermes --today
token-stats -b claude-code --today
token-stats -b codex --today
token-stats -b openclaw --today

# 昨天
token-stats -b hermes --yesterday

# 本周（周一到现在）
token-stats -b hermes --week

# 最近 7 天
token-stats -b hermes --last-7d

# 自定义日期范围（从当天 00:00:00 到当天 23:59:59）
token-stats -b hermes --from 2026-01-01 --to 2026-05-18
token-stats -b claude-code --from 2026-01-01 --to 2026-05-18
```

时间段输出示例（无上下文占比，显示会话数）：
```
📊 Hermes
  deepseek-v4-flash | 总计 988.9K | 输入 660.5K | 输出 327.0K | 缓存 72.66M | 调用 699 次 | 4 轮会话
```

### 对比两个时间段

```bash
# 快捷标签对比
token-stats -b hermes --compare --a today --b yesterday
token-stats -b hermes --compare --a this-week --b last-week

# 单天对比
token-stats -b hermes --compare --a 2026-01-01 --b 2026-05-18
token-stats -b claude-code --compare --a 2026-01-01 --b 2026-05-18

# 时间段对比（YYYY-MM-DD~YYYY-MM-DD）
token-stats -b hermes --compare --a 2026-01-01~2026-01-07 --b 2026-01-08~2026-05-18
```

对比输出示例：
```
📊 对比: "today" vs "yesterday"  [Hermes]
══════════════════════════════════════════════════════════════════════
  模型                           |            A |            B |           变化
──────────────────────────────────────────────────────────────────────
  deepseek-v4-flash            |       988.9K |        65.4K |      -923.5K
──────────────────────────────────────────────────────────────────────
  总计                           |       988.9K |        65.4K |      -923.5K
```

### 导出数据

交互式选择目录和格式：

```bash
# 导出当前最新会话
token-stats -b hermes --export
token-stats -b claude-code --export
token-stats -b codex --export

# 导出今天的数据
token-stats -b hermes --today --export

# 导出昨天的数据
token-stats -b hermes --yesterday --export

# 导出过去 7 天
token-stats -b hermes --last-7d --export

# 导出指定时间段
token-stats -b hermes --from 2026-01-01 --to 2026-05-18 --export

# 导出多个 Agent（逗号分隔）
token-stats -b hermes,claude-code --export

# 导出本机所有 Agent
token-stats --all --export

# 导出多 Agent + 时间段（以下组合均支持）
token-stats -b hermes,claude-code --today --export          # 多个 Agent 的今日统计
token-stats --all --today --export                          # 所有 Agent 的今日统计
token-stats --all --from 2026-01-01 --to 2026-05-18 --export  # 所有 Agent 的指定时间段
token-stats -b hermes,claude-code --yesterday --export      # 多个 Agent 的昨日统计
token-stats -b hermes,claude-code --week --export           # 多个 Agent 的本周统计
```

 流程：先显示格式化汇总 → 请输入导出目录路径 → 选择 JSON 还是 CSV。

 **单 Agent 导出包含每个模型的明细 + 合计行（多模型时）：**
 ```text
 📊 Hermes — 导出 (2026-05-18)
 ════════════════════════════════════════════════════
   deepseek-v4-flash
     上下文          178.4K /   1.05M (17.0%)
     输入 tokens     115.1K
     输出 tokens      63.3K
     缓存 tokens     18.10M
     调用次数        192 次 (今日: 24 次)
     ─────────────────────────────────────
     总计 tokens     178.4K
     总计 + 缓存     18.28M

   claude-sonnet-4
     上下文           85.5K /  200.0K (42.8%)
     输入 tokens      52.2K
     输出 tokens      33.3K
     缓存 tokens      2.00M
     调用次数         10 次 (今日: 24 次)
     ─────────────────────────────────────
     总计 tokens      85.5K
     总计 + 缓存      2.09M

   ──────────────────────────────────────────    ← 多模型时自动显示合计
   合计
     输入 tokens     167.3K
     输出 tokens      96.6K
     缓存 tokens     20.10M
     调用次数        202 次
     ─────────────────────────────────────
     总计 tokens     263.9K
     总计 + 缓存     20.36M
 ```

 **多 Agent 导出（`--all --export` 或 `-b a,b --export`）：**
 每个 Agent 独立展示，末尾汇总全部 Agent 总计。
 JSON 输出使用 `"agents": [...]` 结构，CSV 增加 `Agent` 列区分。

  支持三大操作系统路径：
- macOS/Linux: `~/Desktop`, `/tmp/data`
- Windows: `C:\Users\xxx\Documents`

### 实时监控

```bash
# 交互式选择 → 监控
token-stats --watch

# 直接指定
token-stats -b hermes --watch
token-stats -b claude-code --watch 2   # 2 秒刷新一次
```

每 N 秒自动刷新（默认 5 秒），Ctrl+C 停止后输出汇总表和监控期间总增量。

输出示例（单模型）：
```text
── [05:30:45] +347 tokens (+1 调用) ──
  deepseek-v4-flash | 上下文 119.2K/1.05M (11.4% ✅) | 输入 +333/82.6K tokens | 输出 +14/36.6K tokens | 缓存 +103.0K/7.93M tokens | 调用 +1/115
  deepseek-v4-flash | 输入 480.0K tokens | 输出 120.0K tokens | 总计 600.0K tokens | 缓存 8.50M tokens | 调用 22 次       ← 今日累计

── [05:30:50] 无变化 ──                                    ← 无变化时只一行，不显示模型行
```

输出示例（多模型，每模型一行今日数据 + 合计行）：
```text
── [05:30:55] +1.2K tokens (+2 调用) ──
  deepseek-v4-flash | 上下文 178.4K/1.05M (17.0% ✅) | 输入 +968/115.1K tokens | 输出 +232/63.3K tokens | ...
  claude-sonnet-4    | 上下文 85.5K/200K (42.8%) | 输入 +87/52.2K tokens | 输出 +40/33.2K tokens | ...
  deepseek-v4-flash | 输入 481.2K tokens | 输出 120.2K tokens | 总计 601.4K tokens | 缓存 8.81M tokens | 调用 24 次
  claude-sonnet-4   | 输入 200.1K tokens | 输出 50.1K tokens | 总计 250.2K tokens | 缓存 2.01M tokens | 调用 11 次
  ──────────────────────────────────────────────────────────────────────────────────────────────────
  合计              | 输入 681.3K tokens | 输出 170.3K tokens | 总计 851.6K tokens | 缓存 10.82M tokens | 调用 35 次
```

**实时监控能告诉你：**
- 当前会话的上下文占比还有多少余量（`上下文 119.2K/1.05M (11.4% ✅)`）
- 每一轮对话的**输入/输出/缓存**各自增量和累计量
- 大模型调用次数：**本轮增量 / 窗口累计**
- 上下文窗口是否快要占满（>90% 🚨 提示），避免模型静默丢弃最早的消息
- 监控结束后汇总监控期间的总消耗，方便对比不同会话的开销

**不考虑做这件事的后患：**

长时间不新建会话继续对话，虽然模型不会崩，但会有三个实际代价：

1. **每轮成本指数级上升** — 上下文 800K 时每轮输入 ≈ 800K tokens，10 轮可能烧掉 $1+；新建会话后每轮仅输入几个 K，几乎免费
2. **响应越来越慢** — 模型处理 1M 上下文比 100K 慢得多，你能感觉到打字后等更久才出第一个字
3. **模型静默丢消息** — 超过上下文上限后，模型会丢弃最旧的消息，但你**不会收到任何提示**。问"刚刚说的还记不记得？"时模型可能自信地编一个假答案

> 💡 **建议策略**：
> - 超过 **60%** → 输入 `/compact`（压缩上下文，比 `/new` 快且保留关键信息）
> - 超过 **90%** → 输入 `/new`（清空上下文，从零开始）
>
> 以上命令在 **所有平台通用**（CLI 终端、IDE 插件、QQ/钉钉等聊天 App 均支持斜杠命令）。
> IDE 插件通常还提供工具栏按钮（「压缩上下文」「新建对话」），效果与命令相同。
>
> 关键信息（偏好、项目结构、配置）通过记忆或笔记带走，不要只依赖上下文。

### 查看本机装了哪些 Agent

```bash
token-stats --list-backends
```

✅ 表示已安装，❌ 表示没装。没装的 Agent 不会出现在菜单里。

---

## 命令大全

所有命令都支持将 `-b hermes` 中的 `hermes` 替换为：`claude-code`、`codex`、`openclaw`。

### 基础

| 命令 | 说明 |
|------|------|
| `token-stats` | 交互式菜单选择 Agent → 查看统计 |
| `token-stats -b <name>` | 直接指定 Agent，跳过菜单 |
| `token-stats --version` | 显示版本号 |
| `token-stats -b <name> --detail` | 详细模式（同默认） |
| `token-stats -b <name> --now` | 当前快照（同默认） |

### 快速时间段

| 命令 | 说明 |
|------|------|
| `token-stats -b <name> --today` | 今日统计（当天 00:00:00 ~ 现在） |
| `token-stats -b <name> --yesterday` | 昨日统计（昨天全天） |
| `token-stats -b <name> --week` | 本周统计（周一开始至今） |
| `token-stats -b <name> --last-7d` | 最近 7 天 |
| `token-stats -b <name> --from 2026-01-01 --to 2026-05-18` | 自定义时间段（起始日 00:00 到结束日 23:59） |

### 对比

| 命令 | 说明 |
|------|------|
| `token-stats -b <name> --compare --a today --b yesterday` | 快捷标签对比 |
| `token-stats -b <name> --compare --a this-week --b last-week` | 本周 vs 上周 |
| `token-stats -b <name> --compare --a 2026-01-01 --b 2026-05-18` | 两个单天对比 |
| `token-stats -b <name> --compare --a 2026-01-01~2026-01-07 --b 2026-01-08~2026-05-18` | 自定义时间段对比 |

**`--a` / `--b` 支持的格式：**
- `today` — 今天
- `yesterday` — 昨天
- `this-week` — 本周（周一起）
- `last-week` — 上周
- `2026-01-01` — 单天
- `2026-01-01~2026-01-07` — 时间段（起始~结束）

### 导出

| 命令 | 说明 |
|------|------|
| `token-stats -b <name> --export` | 导出当前统计（交互式选目录和格式） |
| `token-stats -b <name> --today --export` | 导出今日统计 |
| `token-stats -b <name> --yesterday --export` | 导出昨日统计 |
| `token-stats -b <name> --last-7d --export` | 导出近 7 天统计 |
| `token-stats -b <name> --from 2026-01-01 --to 2026-05-18 --export` | 导出指定时间段统计 |
| `token-stats -b <name1>,<name2> --export` | 导出多个 Agent（逗号分隔） |
| `token-stats --all --export` | 导出本机所有 Agent |

### 实时监控

| 命令 | 说明 |
|------|------|
| `token-stats --watch` | 交互式选 Agent → 每 5 秒刷新（Ctrl+C 停止） |
| `token-stats -b <name> --watch` | 直接指定 Agent，默认 5 秒 |
| `token-stats -b <name> --watch 10` | 自定义间隔 10 秒 |

### 多 Agent

| 命令 | 说明 |
|------|------|
| `token-stats --all` | 查看本机所有 Agent 统计 |
| `token-stats -b <name1>,<name2>` | 同时查看多个 Agent（逗号分隔） |
| `token-stats --all --export` | 导出所有 Agent 统计 |
| `token-stats --list-backends` | 列出已安装的 Agent |

### 安装与维护

| 命令 | 说明 |
|------|------|
| `clawhub install agent-usage-stats` | 从 ClawHub 安装 |
| `token-stats --setup` | 创建全局命令 + 自动加入 PATH |
| `token-stats --uninstall` | 删除全局命令 + 自动清理 PATH |

> 💡 以上所有命令也可以通过 `token-stats --help` 在线查看。

---

## 各 Agent 的数据怎么看

每次运行输出都以 `📊 Agent名称` 开头，下面每行是一个**有数据的模型**（未使用的不显示）。

| Agent | 能看到什么 |
|-------|-----------|
| **Hermes** | 当前会话的模型、上下文占用（占比 + 提示）、输入/输出/cache tokens、API 调用次数、会话轮数 |
| **Claude Code** | 各模型的上下文占用、调用次数、子代理次数、会话/项目总数 |
| **CodeX** | 各模型的线程数（tokens 在 CodeX 中可能为 0，此时仅显示会话数） |
| **OpenClaw** | 当前模型（含 provider）、上下文占用、输入/输出 tokens、Agent 数量 |

### 数据来源位置（便于排查问题）

| Agent | 数据读哪里 |
|-------|-----------|
| Hermes | `~/.hermes/state.db` → sessions 表 |
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| CodeX | `~/.codex/state_*.sqlite` → threads 表 |
| OpenClaw | `~/.openclaw/agents/main/sessions/` |

### Windows + WSL2 用户

如果 Agent 跑在 WSL2 中，`token-stats` 在 Windows 侧运行时通过 `\\wsl.localhost` 路径访问数据。需满足：

1. **WSL 发行版需处于运行状态** — 打开一个 WSL 终端即可
2. **读取时 Agent 可能锁定数据库** — Hermes 运行时 `state.db` 被锁，关闭 Hermes 后可正常读取
3. **代理冲突** — 如果本机开了 VPN/代理，WSL 网络可能受影响（`wsl: 检测到 localhost 代理配置`），但不影响本地文件访问

> 如果数据读取失败，可以直接在 WSL 内安装 `token-stats`：
> ```bash
> wsl ~
> cd ~
> clawhub install agent-usage-stats
> python3 ~/skills/agent-usage-stats/token-stats.py setup
> token-stats --all
> ```

### 支持的模型（69 个模型，13 个厂商）

`token-stats` 自动识别模型并显示正确的上下文窗口大小。未匹配的模型默认 128K。

| 厂商 | 模型 | 上下文 |
|------|------|--------|
| **Anthropic / Claude** | `claude-opus-4-7`, `claude-opus-4-5`, `claude-opus-4`, `claude-sonnet-4-6`, `claude-sonnet-4-5`, `claude-sonnet-4`, `claude-haiku-4-5`, `claude-haiku-3.5`, `claude-3.5-sonnet`, `claude-3.5-haiku`, `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku` | 200K |
| **OpenAI / GPT** | `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano` | 1M |
| | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-4` | 128K |
| | `o4-mini`, `o3`, `o3-mini`, `o1`, `o1-pro` | 200K |
| **Google / Gemini** | `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.0-flash` | 1M |
| **DeepSeek** | `deepseek-v4-pro`, `deepseek-v4-flash`, `deepseek-v4`, `deepseek-chat`, `deepseek-reasoner`, `deepseek-r1` | 1M |
| | `deepseek-v3` | 128K |
| **通义千问 / Qwen** | `qwen3`, `qwen3-coder`, `qwen2.5-coder`, `qwen-plus`, `qwen-max`, `qwen-turbo` | 128K |
| **Kimi / 月之暗面** | `moonshot-v1-128k`, `moonshot-v1-32k`, `moonshot-v1-8k`, `kimi-latest` | 8K~128K |
| **GLM / 智谱** | `glm-4-plus`, `glm-4-long` (1M), `glm-4-air`, `glm-4-flash`, `glm-4`, `glm-3-turbo` | 128K~1M |
| **Doubao / 字节豆包** | `doubao-pro-128k`, `doubao-pro-32k`, `doubao-lite-32k` | 32K~128K |
| **文心 / 百度** | `ernie-4.0-turbo`, `ernie-4.0`, `ernie-3.5` | 8K~128K |
| **Meta / Llama** | `llama-4`, `llama-3.1`, `llama-3` | 128K |
| **Mistral** | `mistral-large-2`, `mistral-large`, `mistral-small` | 128K |
| **xAI / Grok** | `grok-3`, `grok-2` | 128K |
| **零一万物 / Yi** | `yi-large`, `yi-lightning` | 16K~32K |

前缀匹配支持: `claude-opus-4-7-20250219` → 200K, `gpt-4.1-preview` → 1M, `deepseek-v4-0324` → 1M。

---

## 实用场景

**想知道 Hermes 用了多少上下文？**
```bash
token-stats
# 选 1 → 看到 "上下文: 123.4K/1M (11.8% ✅)"
```

**边用 Claude Code 边盯着消耗？**
```bash
token-stats -b claude-code --watch
# 切到 Claude Code 干活，这边实时跳动 tokens
```

**想换 Agent 了？**
```bash
token-stats
# 再选一次就行
```

---

## 卸载

```bash
# 第 1 步：清理全局命令 + PATH（自动）
token-stats --uninstall

# 第 2 步：移除技能文件
clawhub uninstall agent-usage-stats
```

> `--uninstall` 会自动删除包装器、清理 PATH 条目、删除配置文件。三平台统一。

---

## 兼容性

| 平台 | 状态 |
|------|------|
| macOS | ✅ 完整支持 |
| Linux | ✅ 完整支持 |
| Windows | ✅ 支持（`.cmd` 包装器） |

| 环境 | 要求 |
|------|------|
| Python | 3.8+（标准库，零 pip 依赖） |
| Node.js | 仅安装时需要（装 ClawHub） |

---

## 常见问题与排查指南

### 安装问题

#### ❓ `clawhub install agent-usage-stats` 报错

**可能原因：网络问题或 Node.js 版本过旧。**

```bash
# 检查 Node.js 版本（需要 v18+）
node --version

# 重装 ClawHub
npm install -g clawhub

# 如果在国内网络慢，可尝试
npm install -g clawhub --registry=https://registry.npmmirror.com
```

<a id="setup-not-found"></a>
#### ❓ 安装文件路径异常排查

**适用场景：执行 `setup` 时提示文件不存在。**

**原因：没有先 `cd ~` 再执行 `clawhub install`**，技能被装到了其他目录。

**解决：**
```bash
cd ~
clawhub install agent-usage-stats --force
```

然后按上方安装指引执行 `setup`。主目录 (`~`) 在所有系统上都有写入权限，不会出现权限问题。

<a id="ps-tilde"></a>
#### ❓ PowerShell 报 `can't open file '...~...'`

**原因：PowerShell 作为命令行参数传递 `~` 时不会展开**，`~` 被当作字面量目录名。

错误示例：
```
python: can't open file 'C:\\Users\\xxx\\~\\skills\\...': No such file or directory
```

**解决：用 `$HOME` 替代 `~`：**
```powershell
# ❌ 错误
python ~\skills\agent-usage-stats\token-stats.py setup

# ✅ 正确
python $HOME\skills\agent-usage-stats\token-stats.py setup
```

> `$HOME` 是 PowerShell 内置变量，始终展开为当前用户目录。

#### ❓ `token-stats` 命令找不到

**原因 1：还没执行 `setup`** → 按上方安装指引执行 `python $HOME\skills\...\token-stats.py setup`（Windows）或 `python3 ~/skills/.../token-stats.py setup`（macOS/Linux）。

**原因 2：执行了 `setup` 但没新开终端** → `setup` 已将 PATH 写入系统配置，但当前终端不生效，新开一个终端即可。

**原因 3：setup 执行失败** → 重新执行 `setup`，观察是否有报错。如果 PATH 添加失败，可手动添加：

**macOS（zsh）：**
```bash
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc
source ~/.zshrc
```

**Linux（bash）：**
```bash
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.bashrc
source ~/.bashrc
```

**Windows（PowerShell 临时）：**
```powershell
$env:PATH += ';' + "$env:USERPROFILE\.local\bin"
```

#### ❓ 执行 `token-stats` 报 `Permission denied`

**仅 macOS / Linux。原因：包装器脚本没有执行权限。**

```bash
chmod +x ~/.local/bin/token-stats
# 或者重新执行 setup
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

> Windows 用户不受此问题影响（`.cmd` 文件不需要执行权限）。

### 运行问题

#### ❓ 菜单里看不到我装的 Agent

**原因：`token-stats` 通过检查特定路径来判断 Agent 是否已安装。** 这些路径存在才会显示：

| Agent | 检测路径 |
|-------|---------|
| **Hermes** | `~/.hermes/state.db` |
| **Claude Code** | `~/.claude/projects/` |
| **CodeX** | `~/.codex/state_*.sqlite` |
| **OpenClaw** | `~/.openclaw/agents/main/sessions/sessions.json` |

可以先用 `token-stats --list-backends` 看具体哪个被检测到了。

#### ❓ 统计显示「无数据」或数字为 0

**可能原因：**

1. **Agent 虽然装了但还没使用过** → 先去用一下再回来查
2. **数据文件路径不对** → 运行 `token-stats --list-backends` 确认是否被检测到
3. **时间段内没有数据** → 如果是 `--today` 或 `--from 2026-01-01`，确认该时间段内确实有会话

#### ❓ 对比结果显示 `unknown` 模型

**Hermes 数据库中部分会话的 model 字段为空**，不影响正常统计。可以用这个命令排查：

```bash
sqlite3 ~/.hermes/state.db "SELECT DISTINCT model FROM sessions WHERE model IS NULL OR model = ''"
```

> Windows 用户如果没有 `sqlite3` 命令，可以用 Python 替代：
> ```powershell
> python3 -c "import sqlite3; c=sqlite3.connect(r'$env:USERPROFILE\.hermes\state.db'); print('\n'.join(r[0] or '(NULL)' for r in c.execute('SELECT DISTINCT model FROM sessions WHERE model IS NULL OR model = \"\"')))"
> ```
