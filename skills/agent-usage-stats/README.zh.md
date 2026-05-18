# token-stats — 选个 Agent 看它的消耗

每次运行都让你选，想看哪个 Agent 就看哪个。

## 为什么选择 token-stats

`token-stats` 直接读取本地数据，跨 Agent、跨模型、跨平台运行。零依赖，纯 Python 标准库。

| 功能 | 命令 | 说明 |
|------|------|------|
| **Token 消耗统计** — 指定时间范围 | `token-stats -a hermes --today` | 多 Agent（Hermes / Claude Code / CodeX / OpenClaw）、多模型，输入/输出/缓存 token 和调用次数，有数据才展示 |
| **实时监控** — 上下文占比追踪 | `token-stats -a hermes --watch` | 每轮增量 + 累计量，超 90% 预警，macOS / Linux / Windows 通用 |
| **时段对比** — 两个时间段并排比较 | `--compare --a today --b yesterday` | 任意时间段聚合，多模型横向对比，带差值列 |
| **数据导出** — JSON / CSV | `--export` | 多 Agent、多时间段组合，交互式选目录 |
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
# 输出: token-stats v2.3.6

# 验证 2：看本机已安装的 Agent
token-stats --list-backends
# 输出示例:
#   ✅ Hermes
#   ✅ Claude Code
#   ❌ CodeX
#   ❌ OpenClaw

# 验证 3：直接看某个 Agent 的统计
token-stats -a hermes
# 输出示例:
# 📊 Hermes
#   deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 调用 13 次
```

如果以上三条都正常输出，说明安装完全成功 🎉

## 更新

```bash
clawhub update agent-usage-stats
token-stats --version
```

> `update` 原地替换文件，包装器和 PATH 均无需重配。

> 💡 更新后版本没变？加 `--force` 强制拉取：
> ```
> clawhub install agent-usage-stats --force
> ```

---

## 用法

`-b` 支持 `hermes` / `claude-code` / `codex` / `openclaw`，逗号分隔可查多个。

```bash
# 当前快照
token-stats                           # 交互式选择
token-stats -a hermes                 # 直接指定
token-stats -a hermes,claude-code     # 多 Agent
token-stats --all                     # 所有 Agent

# 时间段
token-stats -a hermes --today         # 今日
token-stats -a hermes --yesterday     # 昨日
token-stats -a hermes --week          # 本周
token-stats -a hermes --from 2026-01-01 --to 2026-05-18

# 对比
token-stats -a hermes --compare --a today --b yesterday

# 导出
token-stats -a hermes --export
token-stats --all --today --export

# 实时监控
token-stats -a hermes --watch
token-stats -a claude-code --watch 2  # 2 秒刷新

# 维护
token-stats --list-backends           # 列出已安装的 Agent
token-stats --setup                   # 安装全局命令
token-stats --uninstall               # 卸载
```

输出示例（当前快照）：
```
📊 Hermes
  deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 缓存 480.6K | 调用 13 次

📊 Claude Code
  deepseek-v4-pro | 总计 11.83M | 输入 8.07M | 输出 3.76M | 缓存 2116.08M | 调用 8274 次
```

输出示例（时间段）：
```
📊 Hermes
  deepseek-v4-flash | 总计 988.9K | 输入 660.5K | 输出 327.0K | 缓存 72.66M | 调用 699 次 | 4 轮会话
```

### 常见场景

```bash
# 今天所有 Agent 的消耗
token-stats --all --today

# 今天指定 Agent + 导出
token-stats -a hermes --today --export

# 本周 Claude Code 的用量
token-stats -a claude-code --week

# 本月所有 Agent 统计并导出
token-stats --all --from 2026-05-01 --to 2026-05-31 --export

# 今天 vs 昨天对比
token-stats -a hermes --compare --a today --b yesterday

# 指定时间段对比
token-stats -a hermes --compare --a 2026-01-01~2026-01-07 --b 2026-01-08~2026-01-14

# 多 Agent 指定时间段
token-stats -a hermes,claude-code --from 2026-05-01 --to 2026-05-18

# 全 Agent 今天数据导出 JSON
token-stats --all --today --export

# 实时监控（边聊边看，Ctrl+C 停止看汇总）
token-stats -a hermes --watch
```

### 上下文占比提醒

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

## 实用场景

**想知道 Hermes 用了多少上下文？**
```bash
token-stats
# 选 1 → 看到 "上下文: 123.4K/1M (11.8% ✅)"
```

**边用 Claude Code 边盯着消耗？**
```bash
token-stats -a claude-code --watch
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
