# token-stats — 选个 Agent 看它的消耗

每次运行都让你选，想看哪个 Agent 就看哪个。

## 为什么选择 token-stats

`token-stats` 直接读取本地数据，跨 Agent、跨模型、跨平台运行。零依赖，纯 Python 标准库。

| 功能 | 命令 | 说明 |
|------|------|------|
| **Token 消耗统计** — 指定时间范围 | `token-stats -a claude-code --month` | 多 Agent（Hermes / Claude Code / CodeX / OpenClaw）、多模型，输入/输出/缓存 token 和调用次数，有数据才展示 |
| **实时监控** — 上下文占比追踪 | `token-stats -a claude-code --watch` | 每轮增量 + 累计量，超 90% 预警，macOS / Linux / Windows 通用 |
| **时段对比** — 两个时间段并排比较 | `--compare --a today --b yesterday` | 任意时间段聚合，多模型横向对比，带差值列 |
| **数据导出** — XLSX / JSON | `--export` | 多 Agent、多时间段组合，交互式选目录；年度按月拆分 |
| **模型识别** — 中转站 API 校验 | `token-stats -a <name>` | 自动识别 API 返回的模型名称（69 个模型 13 个厂商） |

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
>
> 🕐 **时区说明**：`--today` / `--yesterday` 等时间段基于**本机系统时区**。例如北京时间 (UTC+8) 的 `--today` 统计范围为当日 00:00~23:59 CST。跨时区机器看到的数据范围不同。

### API 中转站

通过中转站访问大模型时，统计准确性取决于中转站是否**原样透传** API 返回的 `usage` 字段。`token-stats` 只记录 Agent 本地写入的数据，不校验与上游 API 是否一致。

### 统计原理

`token-stats` 读取各 Agent 写入本地的数据文件（SQLite / JSONL），按模型聚合 `usage` 对象中的 `input_tokens`、`output_tokens`、`cache_read_tokens` 和调用次数。数据链路：

```
API 返回 usage → Agent 写入本地 → token-stats 读取汇总
```

统计结果可能与 API 结算后台存在偏差，原因：
- **缓存 token 叠加**：`cache_read_tokens` 可能被多次计入（每轮缓存命中都计数）
- **Agent 未完整记录**：部分 Agent/版本不记录 `tool_call_count` 等字段
- **时区差异**：API 后台使用 UTC，本工具使用本地时区
- **中转站改写**：中转站可能修改或移除 `usage` 字段

> 本工具定位为**本地账本**，呈现的是 Agent 记录的数据，非上游结算依据。

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
# 输出: token-stats v2.4.5

# 验证 2：看本机已安装的 Agent
token-stats --list-backends
# 输出示例:
#   ✅ Hermes
#   ✅ Claude Code
#   ✅ CodeX
#   ❌ OpenClaw

# 验证 3：直接看某个 Agent 的统计
token-stats -a claude-code
# 输出示例:
# 📊 Claude Code
#   Qwen3-Coder-30B-A3B-Instruct-MLX-4bit | 入 22.91K | 出 131    | 缓 0       | 总计/+缓存 23.04K/0      | 调用 1 次
#   deepseek-v4-flash                     | 入 2.02M  | 出 77.48K | 缓 8.36M   | 总计/+缓存 2.1M/8.36M    | 调用 349 次
#   deepseek-v4-pro                       | 入 4.9M   | 出 1.19M  | 缓 451.87M | 总计/+缓存 6.09M/451.87M | 调用 2348 次
#   gemma-4-26B-A4B-it-MLX-4bit           | 入 89.18K | 出 1.08K  | 缓 0       | 总计/+缓存 90.26K/0      | 调用 4 次
#   合计                                  | 入 7.03M  | 出 1.27M  | 缓 460.24M | 总计/+缓存 8.3M/460.24M  | 调用 2702 次
```

如果以上三条都正常输出，说明安装完全成功 🎉

## 更新

通过 ClawHub 更新到最新版本：

```bash
token-stats update
# 或
clawhub update agent-usage-stats
```

> `update` 原地替换文件，包装器和 PATH 均无需重配。

> 💡 更新后版本没变？加 `--force` 强制拉取：
> ```
> clawhub install agent-usage-stats --force
> ```

---

## 用法

### 一分钟速览

| 你想做什么 | 命令 | 适用范围 |
|-----------|------|---------|
| 看看今天用了多少 token | `token-stats --all -t` | **所有 Agent** |
| 看看这个月用了多少 | `token-stats --all -m` | **所有 Agent** |
| 只看 Claude Code 的数据 | `token-stats -a claude-code` | **单个 Agent** |
| 边聊边看消耗跳动 | `token-stats -a claude-code -w` | **单个 Agent** |
| 对比这周和上周 | `token-stats -a claude-code --compare --a this-week --b last-week` | **单个 Agent** |
| 导出到 Excel | `token-stats -a claude-code -m -e` | **单个 / 所有 Agent** |
| 弹出菜单自己选 | `token-stats` | 交互式选择 |

### 常用参数

| 短参数 | 长参数 | 干什么用的 |
|:---:|---|---|
| `-a` | `--agent` | 指定要看哪个 Agent：`hermes` / `claude-code` / `codex` / `openclaw`。多个用逗号隔开 |
| `-t` | `--today` | 只看今天的数据 |
| `-m` | `--month` | 看本月（1 号到今天）的数据 |
| `-y` | `--year` | 看今年（1 月 1 号到今天）的数据 |
| `-w` | `--watch` | 实时监控，每 5 秒刷新一次，Ctrl+C 停止 |
| `-e` | `--export` | 导出成 Excel / CSV / JSON 文件 |
| `-v` | `--version` | 查看当前版本号 |
| `-l` | `--list-backends` | 看看电脑上装了哪些 AI 助手 |
| `--all` | | 一次性查看**所有** Agent 的统计 |

> 💡 短参数可以组合。比如 `-a claude-code -t -e` 表示"只看 Claude Code，今天的数据，导出"。

---

### 一、我想看某一个 Agent 的数据

这里以 Claude Code 为例。把 `claude-code` 换成你用的 Agent 就行（`hermes` / `codex` / `openclaw`）。

**直接看全部历史（不限时间段）：**

```bash
token-stats -a claude-code
```

**只看今天的：**

```bash
token-stats -a claude-code -t
```

**看昨天的：**

```bash
token-stats -a claude-code --yesterday
```

**看本月的（1 号到今天）：**

```bash
token-stats -a claude-code -m
```

**看今年的（1 月 1 号到今天）：**

```bash
token-stats -a claude-code --year
```

**看本周的（周一到今天）：**

```bash
token-stats -a claude-code --week
```

**看最近 7 天的：**

```bash
token-stats -a claude-code --last-7d
```

**自己指定日期范围：**

```bash
# 从 1 月 1 号到 5 月 18 号
token-stats -a claude-code --from 2026-01-01 --to 2026-05-18
```

输出长这样：

```
📊 Claude Code
  deepseek-v4-flash | 入 2.02M | 出 77.48K | 缓 8.36M | 总计/+缓存 2.1M/10.46M | 调用 349 次
  deepseek-v4-pro   | 入 4.9M  | 出 1.19M  | 缓 451.87M | 总计/+缓存 6.09M/457.96M | 调用 2348 次
  合计              | 入 6.93M | 出 1.27M  | 缓 460.24M | 总计/+缓存 8.2M/468.44M | 调用 2702 次
  ────────────────────────────────────
  子代理: 17 次 | 会话: 20 个 | 项目: 4 个
```

---

### 二、我想同时看多个 Agent 的数据

**指定要看哪几个（逗号分隔）：**

```bash
# 同时看 Hermes 和 Claude Code 本月的数据
token-stats -a hermes,claude-code -m
```

**一次性看电脑上所有 Agent 的数据：**

```bash
# 全部历史（不限时间段）
token-stats --all

# 所有 Agent 今天的数据
token-stats --all -t

# 所有 Agent 本月的数据
token-stats --all -m

# 所有 Agent 今年的数据
token-stats --all --year
```

输出长这样：

```
📊 本机 Agent 统计汇总
══════════════════════════════════════════════════

✅ Hermes
📊 Hermes
  deepseek-v4-flash | 上下文 92.42K/1.05M (8.8%) | 入 83.5K | 出 8.92K | 缓 969.22K | 总计/+缓存 92.42K/1.06M | 调用 29 次

✅ Claude Code
📊 Claude Code
  deepseek-v4-flash | 入 2.02M | 出 77.48K | 缓 8.36M | 总计/+缓存 2.1M/10.46M | 调用 349 次
  deepseek-v4-pro   | 入 4.9M  | 出 1.19M  | 缓 451.87M | 总计/+缓存 6.09M/457.96M | 调用 2348 次
  合计              | 入 7.03M | 出 1.27M  | 缓 460.24M | 总计/+缓存 8.3M/468.54M | 调用 2702 次

══════════════════════════════════════════════════
  全部 Agent 总计
  入 7.12M | 出 1.28M | 缓 461.21M | 总计/+缓存 8.4M/469.61M | 调用 2734 次
```

---

### 三、我想看看电脑上装了哪些 AI 助手

```bash
# 短参数
token-stats -l

# 长参数
token-stats --list-backends
```

输出长这样：

```
本机已安装的 AI 助手：
  ✅ Hermes
  ✅ Claude Code
  ✅ CodeX
  ❌ OpenClaw
```

> ✅ = 检测到了，可以查。❌ = 没装或没数据。

---

### 四、我想对比两个时间段

会并排显示两个时间段的 入/出/缓/总计/总计(含缓存)/调用，带差值列，不同模型之间有 `·` 分隔线。

**今天和昨天比：**

```bash
token-stats -a claude-code --compare --a today --b yesterday
```

**这周和上周比：**

```bash
token-stats -a claude-code --compare --a this-week --b last-week
```

**这个月和上个月比：**

```bash
token-stats -a claude-code --compare --a this-month --b last-month
```

**今年和去年比：**

```bash
token-stats -a claude-code --compare --a this-year --b last-year
```

**两个自定义日期比：**

```bash
# 两个具体的某一天
token-stats -a claude-code --compare --a 2026-01-01 --b 2026-01-15

# 两个日期范围（用 ~ 连接）
token-stats -a claude-code --compare --a 2026-01-01~2026-01-07 --b 2026-01-08~2026-01-14
```

支持的标签：`today` / `yesterday` / `this-week` / `last-week` / `this-month` / `last-month` / `this-year` / `last-year` / `YYYY-MM-DD` / `YYYY-MM-DD~YYYY-MM-DD`

输出长这样：

```
📊 对比: 2026-05-18~2026-05-20 vs 2026-05-11~2026-05-17  [Claude Code]
=================================================================================================
  模型              | 指标         | 2026-05-18~2026-05-20 | 2026-05-11~2026-05-17 | 变化
─────────────────────────────────────────────────────────────────────────────────────────────────
  deepseek-v4-flash | 入           | 5.4M                  | 8.09M                 | +2.69M
                    | 出           | 166.37K               | 267.71K               | +101.34K
                    | 缓           | 14.09M                | 40.14M                | +26.05M
                    | 总计         | 5.57M                 | 8.36M                 | +2.79M
                    | 总计(含缓存) | 19.66M                | 48.5M                 | +28.84M
                    | 调用         | 482                   | 1.19K                 | +704
  ································································································
  deepseek-v4-pro   | 入           | 4.43M                 | 6.89M                 | +2.46M
                    | 出           | 2.23M                 | 3.1M                  | +868.87K
                    | 缓           | 890.06M               | 1883.5M               | +993.43M
                    | 总计         | 6.66M                 | 9.99M                 | +3.33M
                    | 总计(含缓存) | 896.72M               | 1893.48M              | +996.76M
                    | 调用         | 4.28K                 | 6.82K                 | +2.54K
  ································································································
  合计              | 入           | 41.99M                | 14.98M                | -27.01M
                    | 出           | 2.48M                 | 3.37M                 | +887.19K
                    | 缓           | 904.15M               | 1923.64M              | +1019.48M
                    | 总计         | 44.47M                | 18.34M                | -26.13M
                    | 总计(含缓存) | 948.62M               | 1941.98M              | +993.36M
                    | 调用         | 5.53K                 | 8K                    | +2.47K
─────────────────────────────────────────────────────────────────────────────────────────────────
```

---

### 五、我想实时监控 token 消耗

边用 Agent 边盯着，每几秒刷新一次，看到数字在跳。Ctrl+C 停止后会显示本次监控的汇总。

**默认 5 秒刷新一次：**

```bash
token-stats -a claude-code -w
```

**自定义刷新间隔（比如 2 秒一次）：**

```bash
token-stats -a claude-code -w 2
```

输出长这样：

```
📡 实时监控 [Claude Code] — 每 5 秒刷新 (Ctrl+C 停止)

初始状态:
  deepseek-v4-flash | 入 2.02M | 出 77.48K | 缓 8.36M | 总计/+缓存 2.1M/10.46M | 调用 349 次
  deepseek-v4-pro   | 入 4.9M  | 出 1.19M  | 缓 451.87M | 总计/+缓存 6.09M/457.96M | 调用 2348 次

── [10:30:00] +1.2K tokens +3 调用 ──
  deepseek-v4-pro | +1K入/4.9M | +200出/1.19M | +1.2K缓/451.87M | +3调用
  ╌╌╌╌╌ 📅 今日 ╌╌╌╌╌
  deepseek-v4-flash | 入 191.65K | 出 999 | 缓 219.9K | 总计/+缓存 192.65K/412.55K | 调用 16
  deepseek-v4-pro   | 入 3.02M   | 出 323.29K | 缓 119.45M | 总计/+缓存 3.34M/122.79M | 调用 624

── [10:30:05] 无新活动 ──

^C
📊 本次监控汇总
  监控时长: 5 分 30 秒 | 采集 66 轮
```

> ⚠️ watch 模式只能看**一个** Agent，不支持 `--all` 或逗号多选。

---

### 六、我想导出数据到文件

支持三种格式：XLSX（Excel）、CSV、JSON。年度导出会自动按月分列。

**导出某一个 Agent 的数据：**

```bash
# 导出 Claude Code 全部历史（会弹出格式选择和目录选择）
token-stats -a claude-code -e

# 导出 Claude Code 今天的数据
token-stats -a claude-code -t -e

# 导出 Claude Code 本月的数据
token-stats -a claude-code -m -e

# 导出 Claude Code 今年的数据（自动按月拆分，每月一列）
token-stats -a claude-code --year -e

# 直接指定导出目录，跳过目录选择（会弹出格式选择）
token-stats -a claude-code -m -e ~/Desktop
```

**导出所有 Agent 的数据：**

```bash
# 所有 Agent 本月的数据
token-stats --all -m -e

# 所有 Agent 今年的数据（按月拆分，一张表包含所有 Agent）
token-stats --all --year -e
```

**选择导出格式：**

运行后会提示你选：
```
选择导出格式:
  [1] XLSX（默认）
  [2] CSV
  [3] JSON
请选择 (1/2/3, 回车=1):
```

直接回车就选 XLSX。也可以用管道提前选好：

```bash
# 选 XLSX（回车=1）
echo 1 | token-stats -a claude-code -m -e ~/Desktop

# 选 CSV
echo 2 | token-stats -a claude-code -m -e ~/Desktop

# 选 JSON
echo 3 | token-stats -a claude-code -m -e ~/Desktop
```

---

### 七、我不想记参数，弹出菜单自己选

什么都不带直接运行，会弹出菜单让你选要看哪个 Agent。

```bash
token-stats
```

```
🔍 选择你要查看的 AI 助手：
────────────────────────────────────────
  [1] Hermes
  [2] Claude Code
  [3] CodeX
  [a] 所有
  [q] 退出
────────────────────────────────────────
请选择：
```

输入数字就能看对应的 Agent。输入 `a` 看所有。

---

---

### 八、工具自身的维护

**查看帮助（所有命令说明）：**

```bash
token-stats --help
```

**查看当前版本号：**

```bash
token-stats -v
# 或
token-stats --version
```

**把 token-stats 更新到最新版：**

```bash
token-stats update
```

如果更新后版本号没变，用强制重装：

```bash
clawhub install agent-usage-stats --force
```

**卸载 token-stats：**

```bash
# 第 1 步：清理全局命令 + PATH
token-stats --uninstall

# 第 2 步：移除技能文件
clawhub uninstall agent-usage-stats
```

---

### 各 Agent 的数据怎么看

| Agent | 当前快照 | 时间段 |
|-------|---------|--------|
| **Hermes** | 上下文占比 + 输入/输出/缓存 + 调用次数 + 会话轮数 | 总计 + 会话数 |
| **Claude Code** | 总计 + 输入/输出/缓存 + 调用次数 + 子代理/项目数 | 同左 |
| **CodeX** | 总计 + 线程数 | 同左 |
| **OpenClaw** | 上下文占比 + 输入/输出/缓存 + 调用次数 | 总计 + 调用数 |

### 数据来源位置（便于排查问题）

| Agent | 数据读哪里 |
|-------|-----------|
| Hermes | `~/.hermes/state.db` → sessions 表 |
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| CodeX | `~/.codex/state_*.sqlite` → threads 表 |
| OpenClaw | `~/.openclaw/agents/main/sessions/` |

### Windows + WSL2 用户

Agent 跑在 WSL2 中时，`token-stats` 在 Windows 侧自动检测并读取数据。即使 Hermes 正在运行（数据库被锁），也会通过 `wsl.exe` 在 WSL 内部读取，输出标注 `(WSL)`。

1. **WSL 发行版需处于运行状态** — 打开一个 WSL 终端即可
2. **用户名无关联** — 自动探测 WSL 内实际用户目录，与 Windows 登录名无关
3. **代理不影响** — VPN/代理只影响 WSL 网络，不影响本地文件访问

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
