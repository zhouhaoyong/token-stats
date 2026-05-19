# token-stats — Pick an Agent, See Its Token Burn

Run it, pick an agent, see the stats. Every time.

## What's this?

You have multiple AI assistants on your machine (Hermes, Claude Code, CodeX, OpenClaw…).
`token-stats` lets you **choose one and see how many tokens it's consuming**.

> ⚠️ **Important: this tool only reads local agent data on this machine.**
> If you run agents on different PCs or servers, each machine stores its own data
> and needs its own installation of `token-stats`. Cross-machine statistics are not supported.
>
> All statistics are queried based on the specific agent you select, not a global total.

---

## Why token-stats

`token-stats` reads local data directly — works across agents, models, and platforms. Zero dependencies, pure Python stdlib.

| Feature | Command | Description |
|---------|---------|-------------|
| **Token stats** — by time range | `token-stats -a hermes --month` | Multi-agent (Hermes / Claude Code / CodeX / OpenClaw), multi-model. Input/output/cache tokens + call counts, only models with data |
| **Live monitor** — context tracking | `token-stats -a hermes --watch` | Per-round delta + cumulative, warns above 90%. macOS / Linux / Windows |
| **Compare** — side-by-side periods | `--compare --a today --b yesterday` | Any time range, multi-model comparison with diff column |
| **Export** — XLSX / JSON | `--export` | Multi-agent, multi-period combinations. Interactive directory picker |
| **Model detect** — proxy API verification | `token-stats -a <name>` | Auto-detects 69 models from 13 providers by actual API response name |

---

## Environment Requirements

Before installing `token-stats`, make sure you have these:

### 1. Python 3.8+

`token-stats` is a pure Python script using only stdlib — no pip packages needed.

```bash
# Check (Windows users: use python --version)
python3 --version

# If missing → https://www.python.org/downloads/
```

### 2. Node.js (needed for the installer)

`token-stats` is distributed via **ClawHub CLI**, a Node.js command-line tool.

```bash
# Check
node --version

# If missing → https://nodejs.org (get the LTS version)
```

Node.js includes `npm`, which is used to install ClawHub.

### 3. ClawHub CLI

```bash
# Install
npm install -g clawhub

# Verify
clawhub -V          # show version
```

> 💡 On macOS with Homebrew-installed Node.js, `npm install -g clawhub` puts it at `/opt/homebrew/bin/clawhub`, which is usually already in your PATH.

> 💡 If you're in China and npm is slow, use the npmmirror registry:
> ```bash
> npm install -g clawhub --registry=https://registry.npmmirror.com
> ```

---

## Install

After meeting the requirements above, two commands:

**macOS / Linux:**
```bash
cd ~
clawhub install agent-usage-stats
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

**Windows (PowerShell):**
```powershell
cd ~
clawhub install agent-usage-stats
python $HOME\skills\agent-usage-stats\token-stats.py setup
```

> `cd ~` ensures the skill installs to your home directory (always writable on all OSes).
> If `python` is not found, try `python3` (Microsoft Store Python uses `python3`).
> If you get `can't open file '...~...'`, see: [PowerShell path expansion](#ps-tilde).
>
> `setup` automatically adds `~/.local/bin` to your system PATH. **Open a new terminal** for it to take effect.

That's it. Open a new terminal and run `token-stats`.

### Verify Installation

```bash
# Check 1: version
token-stats --version
# Output: token-stats v2.3.8

# Check 2: list installed agents
token-stats --list-backends
# Example output:
#   ✅ Hermes
#   ✅ Claude Code
#   ❌ CodeX
#   ❌ OpenClaw

# Check 3: view stats for an agent
token-stats -a hermes
# Example output:
# 📊 Hermes
#   deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 调用 13 次
```

If all three checks produce output, installation is successful 🎉

## Updating

```bash
clawhub update agent-usage-stats
token-stats --version
```

> `update` replaces files in-place — wrapper and PATH carry over, no re-setup required.

> 💡 Version not changing? Use `--force` to pull the latest:
> ```
> clawhub install agent-usage-stats --force
> ```


## Usage

`-a` accepts `hermes` / `claude-code` / `codex` / `openclaw`, comma-separated for multiple.

### Common Scenarios

**Today's token consumption across all agents:**
```bash
token-stats --all -t
```

**This month's usage:**
```bash
token-stats --all -m
```

**Today's consumption for a single agent:**
```bash
token-stats -a claude-code -t
```
Output:
```
📊 Claude Code
  deepseek-v4-flash | 入 191.65K | 出 999     | 缓 219.9K  | 总计/+缓存 192.65K/219.9K | 调用 16 次
  deepseek-v4-pro   | 入 3.02M   | 出 323.29K | 缓 119.45M | 总计/+缓存 3.34M/119.45M  | 调用 624 次
  合计              | 入 3.21M   | 出 324.29K | 缓 119.67M | 总计/+缓存 3.54M/119.67M  | 调用 640 次
```

**Live token tracking:**
```bash
token-stats -a claude-code -w
```

**Weekly comparison (all 6 metrics):**
```bash
token-stats -a claude-code --compare --a this-week --b last-week
```

**Multiple agents at once:**
```bash
token-stats -a hermes,claude-code -m
```
Output:
```
──────────────────────────────────────────────────
  Hermes
──────────────────────────────────────────────────
📊 Hermes
  deepseek-v4-flash | 入 2.03M | 出 819.69K | 缓 223.53M | 总计/+缓存 2.85M/223.53M | 调用 2075 次
──────────────────────────────────────────────────
  Claude Code
──────────────────────────────────────────────────
📊 Claude Code
  deepseek-v4-flash | 入 2.02M | 出 77.48K | 缓 8.36M | 总计/+缓存 2.1M/8.36M | 调用 349 次
  deepseek-v4-pro   | 入 4.92M | 出 1.21M  | 缓 462.77M | 总计/+缓存 6.13M/462.77M | 调用 2387 次
  合计              | 入 7.06M | 出 1.29M  | 缓 471.14M | 总计/+缓存 8.34M/471.14M | 调用 2741 次
══════════════════════════════════════════════════
  全部 Agent 总计
  入 7.14M | 出 1.3M | 缓 472.11M | 总计/+缓存 8.43M/472.11M | 调用 2773 次
```

**List installed agents:**
```bash
token-stats -l
```
Output:
```
本机已安装的 AI 助手：
  ✅ Hermes
  ✅ Claude Code
  ✅ CodeX
  ❌ OpenClaw
```

### Interactive Menu

```bash
token-stats                           # interactive picker
token-stats -a claude-code            # skip menu, go straight to Claude Code
token-stats -a hermes,claude-code     # multiple agents
token-stats --all                     # all agents at once
```

Single agent output:
```
📊 Claude Code
  deepseek-v4-flash | 入 2.02M | 出 77.48K | 缓 8.36M | 总计/+缓存 2.1M/8.36M | 调用 349 次
  deepseek-v4-pro   | 入 4.9M  | 出 1.19M  | 缓 451.87M | 总计/+缓存 6.09M/451.87M | 调用 2348 次
  合计              | 入 6.93M | 出 1.27M  | 缓 460.24M | 总计/+缓存 8.2M/460.24M | 调用 2702 次
```

### Snapshot & Time Ranges

```bash
# Current snapshot (default)
token-stats -a claude-code

# Quick time ranges
token-stats -a claude-code --today         # today
token-stats -a claude-code --yesterday     # yesterday
token-stats -a claude-code --week          # this week (from Monday)
token-stats -a claude-code --last-7d       # last 7 days
token-stats -a claude-code --month         # this month
token-stats -a claude-code --year          # this year

# Custom range
token-stats -a claude-code --from 2026-01-01 --to 2026-05-18
```

Snapshot output:
```
📊 Claude Code
  deepseek-v4-flash | 入 2.02M | 出 77.48K | 缓 8.36M | 总计/+缓存 2.1M/8.36M | 调用 349 次
  deepseek-v4-pro   | 入 4.9M  | 出 1.19M  | 缓 451.87M | 总计/+缓存 6.09M/451.87M | 调用 2348 次
  合计              | 入 6.93M | 出 1.27M  | 缓 460.24M | 总计/+缓存 8.2M/460.24M | 调用 2702 次
```

Time range output:
```
📊 Claude Code
  deepseek-v4-flash | 入 2.02M | 出 77.48K | 缓 8.36M | 总计/+缓存 2.1M/8.36M | 调用 349 次
  deepseek-v4-pro   | 入 4.91M | 出 1.19M  | 缓 452.69M | 总计/+缓存 6.1M/452.69M | 调用 2351 次
  合计              | 入 6.93M | 出 1.27M  | 缓 461.05M | 总计/+缓存 8.2M/461.05M | 调用 2700 次
```

### Live Monitor

Watch token consumption in real time while using your agent:

```bash
token-stats -a claude-code --watch         # refresh every 5s (default)
token-stats -a claude-code --watch 2       # refresh every 2s
```

Output:
```
📡 实时监控 [Claude Code] — 每 5 秒刷新 (Ctrl+C 停止)

初始状态:
  deepseek-v4-flash | 入 2.02M | 出 77.48K | 缓 8.36M | 总计/+缓存 2.1M/8.36M | 调用 349 次
  deepseek-v4-pro   | 入 4.9M  | 出 1.19M  | 缓 451.87M | 总计/+缓存 6.09M/451.87M | 调用 2348 次

── [10:30:00] +1.2K tokens +3 调用 ──
  deepseek-v4-pro | +1K入/4.9M | +200出/1.19M | +1.2K缓/451.87M | +3调用
```

- Context > 60% → suggests `/compact`; > 90% → warning
- `Ctrl+C` to stop and see a monitoring summary

### Compare

Side-by-side comparison of two time periods — all 6 metrics per model:

```bash
# Quick label comparison
token-stats -a claude-code --compare --a today --b yesterday
token-stats -a claude-code --compare --a this-week --b last-week
token-stats -a claude-code --compare --a this-month --b last-month
token-stats -a claude-code --compare --a this-year --b last-year

# Custom date comparison
token-stats -a claude-code --compare --a 2026-01-01 --b 2026-01-15

# Date range comparison
token-stats -a claude-code --compare --a 2026-01-01~2026-01-07 --b 2026-01-08~2026-01-14
```

Output (this week vs last week):
```
📊 对比: 2026-05-18~2026-05-20 vs 2026-05-11~2026-05-17  [Claude Code]
======================================================================================
  模型 | 指标   | 2026-05-18~2026-05-20 | 2026-05-11~2026-05-17 |       变化
──────────────────────────────────────────────────────────────────────────────────────
  deepseek-v4-flash | 入           | 511.35K | 1.51M   | +996.34K
                    | 出           | 19.19K  | 58.29K  | +39.09K
                    | 缓           | 819.97K | 7.54M   | +6.72M
                    | 总计         | 530.55K | 1.57M   | +1.04M
                    | 调用         | 40      | 309     | +269
  deepseek-v4-pro   | 入           | 3.48M   | 1.43M   | -2.05M
                    | 出           | 375.99K | 816.37K | +440.38K
                    | 总计         | 3.86M   | 2.24M   | -1.61M
                    | 调用         | 640     | 1.71K   | +1.07K
  合计              | 入           | 3.99M   | 3.05M   | -943.26K
                    | 出           | 395.18K | 875.86K | +480.68K
                    | 总计         | 4.39M   | 3.92M   | -462.57K
                    | 调用         | 680     | 2.03K   | +1.35K
──────────────────────────────────────────────────────────────────────────────────────
```

Compare labels: `today`, `yesterday`, `this-week`, `last-week`, `this-month`, `last-month`, `this-year`, `last-year`, `YYYY-MM-DD`, `YYYY-MM-DD~YYYY-MM-DD`

### Export

Interactive directory and format picker: `[1] XLSX` / `[2] CSV` / `[3] JSON`:

```bash
# Basic export
token-stats -a claude-code --export

# Export with time range
token-stats -a claude-code --today --export
token-stats -a claude-code --month --export
token-stats -a claude-code --year --export

# All agents export
token-stats --all --today --export
token-stats --all --month --export
token-stats --all --year --export
```

### What each agent shows

| Agent | Snapshot | Time range |
|-------|----------|------------|
| **Hermes** | Context % + input/output/cache + calls + session count | Total + session count |
| **Claude Code** | Total + input/output/cache + calls + sub-agents/projects | Same |
| **CodeX** | Total + thread count | Same |
| **OpenClaw** | Context % + input/output/cache + calls | Total + calls |

### Data sources

| Agent | Reads from |
|-------|-----------|
| Hermes | `~/.hermes/state.db` → sessions table |
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| CodeX | `~/.codex/state_*.sqlite` → threads table |
| OpenClaw | `~/.openclaw/agents/main/sessions/` |

### Windows + WSL2

When your agent runs inside WSL2, `token-stats` automatically detects and reads data from the Windows side. Even if Hermes is running (database locked), it reads via `wsl.exe` internally; output is labeled `(WSL)`.

1. **WSL distro must be running** — open a WSL terminal first
2. **Username agnostic** — auto-detects the WSL user's home directory
3. **Proxy unaffected** — VPN/proxy only affects WSL networking, not local file access

### Supported Models (69 models, 13 providers)

Prefix matching is supported. Unknown models default to 128K.

| Provider | Models | Context |
|----------|--------|---------|
| **Anthropic / Claude** | `claude-opus-4-7`, `claude-opus-4-5`, `claude-opus-4`, `claude-sonnet-4-6`, `claude-sonnet-4-5`, `claude-sonnet-4`, `claude-haiku-4-5`, `claude-haiku-3.5`, `claude-3.5-sonnet`, `claude-3.5-haiku`, `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku` | 200K |
| **OpenAI / GPT** | `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano` | 1M |
| | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-4` | 128K |
| | `o4-mini`, `o3`, `o3-mini`, `o1`, `o1-pro` | 200K |
| **Google / Gemini** | `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.0-flash` | 1M |
| **DeepSeek** | `deepseek-v4-pro`, `deepseek-v4-flash`, `deepseek-v4`, `deepseek-chat`, `deepseek-reasoner`, `deepseek-r1` | 1M |
| | `deepseek-v3` | 128K |
| **Qwen / Alibaba** | `qwen3`, `qwen3-coder`, `qwen2.5-coder`, `qwen-plus`, `qwen-max`, `qwen-turbo` | 128K |
| **Kimi / Moonshot** | `moonshot-v1-128k`, `moonshot-v1-32k`, `moonshot-v1-8k`, `kimi-latest` | 8K~128K |
| **GLM / Zhipu** | `glm-4-plus`, `glm-4-long` (1M), `glm-4-air`, `glm-4-flash`, `glm-4`, `glm-3-turbo` | 128K~1M |
| **Doubao / ByteDance** | `doubao-pro-128k`, `doubao-pro-32k`, `doubao-lite-32k` | 32K~128K |
| **ERNIE / Baidu** | `ernie-4.0-turbo`, `ernie-4.0`, `ernie-3.5` | 8K~128K |
| **Meta / Llama** | `llama-4`, `llama-3.1`, `llama-3` | 128K |
| **Mistral** | `mistral-large-2`, `mistral-large`, `mistral-small` | 128K |
| **xAI / Grok** | `grok-3`, `grok-2` | 128K |
| **Yi / 01.AI** | `yi-large`, `yi-lightning` | 16K~32K |

---

## Common Scenarios

**How much did I spend today?**
```bash
token-stats --all --today
```

**This month — all agents summary**
```bash
token-stats --all --month
```

**This month — all agents export**
```bash
token-stats --all --month --export
```

**This year — all agents export**
```bash
token-stats --all --year --export
```

**This week vs last week**
```bash
token-stats -a hermes --compare --a this-week --b last-week
```

**This month vs last month**
```bash
token-stats -a hermes --compare --a this-month --b last-month
```

**Watch consumption in real time**
```bash
token-stats -a hermes --watch
# Switch to Hermes, watch tokens update live
```

**Multiple agents + time range**
```bash
token-stats -a hermes,claude-code --month
```

---

## Uninstall

```bash
# Step 1: Clean up global command + PATH (automatic)
token-stats --uninstall

# Step 2: Remove skill files
clawhub uninstall agent-usage-stats
```

> `--uninstall` automatically removes the wrapper, cleans the PATH entry, and deletes config files. Works on all platforms.

---

## Compatibility

| Platform | Status |
|----------|--------|
| macOS | ✅ Full support |
| Linux | ✅ Full support |
| Windows | ✅ Supported (`.cmd` wrapper) |

| Requirement | Details |
|-------------|---------|
| Python | 3.8+ (stdlib only, no pip dependencies) |
| Node.js | Required only for installation (ClawHub CLI) |

---

## Troubleshooting

### Installation issues

#### ❓ `clawhub install agent-usage-stats` fails

**Possible cause: network issue or outdated Node.js.**

```bash
# Check Node.js version (needs v18+)
node --version

# Reinstall ClawHub
npm install -g clawhub

# In China with slow network:
npm install -g clawhub --registry=https://registry.npmmirror.com
```

<a id="setup-not-found"></a>
#### ❓ Install path troubleshooting

**When: `setup` fails with file not found.**

**Cause: `clawhub install` was run from a different directory (not home).** Skills are placed under `./skills/` relative to the working directory.

**Fix:**
```bash
cd ~
clawhub install agent-usage-stats --force
```

Then follow the install steps above. The home directory (`~`) is always writable on all OSes.

<a id="ps-tilde"></a>
#### ❓ PowerShell: `can't open file '...~...'`

**Cause: PowerShell does not expand `~` when passed as a command argument**, treating it as a literal directory name.

Error example:
```
python: can't open file 'C:\\Users\\xxx\\~\\skills\\...': No such file or directory
```

**Fix: use `$HOME` instead of `~`:**
```powershell
# ❌ Wrong
python ~\skills\agent-usage-stats\token-stats.py setup

# ✅ Correct
python $HOME\skills\agent-usage-stats\token-stats.py setup
```

> `$HOME` is a built-in PowerShell variable that always expands to the current user directory.

#### ❓ `token-stats` command not found

**Cause 1: Haven't run `setup` yet** → Follow the install steps above.

**Cause 2: Ran `setup` but haven't opened a new terminal** → `setup` writes PATH to system config. Open a new terminal for it to take effect.

**Cause 3: `setup` PATH write failed** → Re-run `setup` and check for errors. If needed, add PATH manually:

**macOS (zsh):**
```bash
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc
source ~/.zshrc
```

**Linux (bash):**
```bash
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.bashrc
source ~/.bashrc
```

**Windows (PowerShell, current session only):**
```powershell
$env:PATH += ';' + "$env:USERPROFILE\.local\bin"
```

#### ❓ `Permission denied` when running `token-stats`

**macOS / Linux only. Cause: wrapper script lacks execute permission.**

```bash
chmod +x ~/.local/bin/token-stats
# Or just re-run setup
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

> Windows users are not affected (`.cmd` files don't need execute permission).

### Runtime issues

#### ❓ My agent isn't showing in the menu

**Cause: `token-stats` checks for specific config files.** These paths must exist:

| Agent | Detection path |
|-------|---------------|
| **Hermes** | `~/.hermes/state.db` |
| **Claude Code** | `~/.claude/projects/` |
| **CodeX** | `~/.codex/state_*.sqlite` |
| **OpenClaw** | `~/.openclaw/agents/main/sessions/sessions.json` |

Run `token-stats --list-backends` to see what's detected.

#### ❓ Stats show "no data" or all zeros

**Possible causes:**

1. **Agent is installed but never used** → use it first, then check again
2. **Data file path is wrong** → confirm with `token-stats --list-backends`
3. **Time range has no data** → if using `--today` or `--from`, check that sessions exist in that period

#### ❓ `unknown` model appears in compare results

**Hermes DB has sessions with empty model field** — doesn't affect accuracy. Diagnose with:

```bash
sqlite3 ~/.hermes/state.db "SELECT DISTINCT model FROM sessions WHERE model IS NULL OR model = ''"
```

> Windows users without `sqlite3` can use Python instead:
> ```powershell
> python3 -c "import sqlite3; c=sqlite3.connect(r'$env:USERPROFILE\.hermes\state.db'); print('\n'.join(r[0] or '(NULL)' for r in c.execute('SELECT DISTINCT model FROM sessions WHERE model IS NULL OR model = \"\"')))"
> ```

#### ❓ Export says "directory not found"

**Cause: the directory path you entered doesn't exist.** Create it first:

```bash
mkdir -p ~/Desktop/my-data
token-stats -a hermes --export
# Enter: ~/Desktop/my-data
```

#### ❓ Install successful but `token-stats` command not found

**Cause:** `clawhub install` was run from a directory other than home, or your system has `~/.openclaw/` (which redirects ClawHub's install target).

**Fix for all OSes:**
```bash
cd ~
clawhub install agent-usage-stats --force
python3 ~/skills/agent-usage-stats/token-stats.py setup   # Windows: python $HOME\skills\...
token-stats --version
```

This ensures the skill is installed to `~/skills/` — the predictable home-directory location.

#### ❓ OpenClaw shows calls but zero tokens

**Cause:** Some OpenClaw versions (especially older builds on Linux) don't record token usage (`input`/`output` counts) in their data files. The tool detects session files and model names, but the `usage` field in `.jsonl` is populated as `0`.

**Notable data:** 0 tokens + non-zero call count → confirms usage recording is missing at the source.

**Resolution:** This is an OpenClaw data recording limitation, not a token-stats bug. Token-stats reads whatever the agent wrote down. Options:
- Upgrade OpenClaw to a newer version that records token usage
- No workaround available in token-stats itself

#### ❓ `--compare` shows no data for both periods

**Possible cause:** neither period has session records. Check with `--today` first.

### Data scope

> ⚠️ `token-stats` **only reads local data. No cross-machine aggregation.**
>
> - **Same API key on multiple machines? → Each machine's stats are isolated**
> - Example: Same key used on PC A and PC B → PC A's `token-stats` only sees PC A's usage
> - `token-stats` reads disk files — no network calls, no API dashboard queries
> - To see another machine's stats, install `token-stats` there too
>
> 🕐 **Timezone**: `--today` / `--yesterday` use your **local system timezone**. E.g. on UTC+8 (Beijing), `--today` spans 00:00–23:59 CST. Machines in different timezones see different ranges.

### API Relay

Stats accuracy depends on whether the relay **passes through** the real API's `usage` field unchanged. `token-stats` reads what your Agent wrote locally — it does not verify against the real API.

### How It Works

`token-stats` reads local data files (SQLite / JSONL) written by each Agent, aggregating `input_tokens`, `output_tokens`, `cache_read_tokens`, and call counts from the `usage` object.

```
API returns usage → Agent writes locally → token-stats reads & aggregates
```

Results may differ from your API billing dashboard because:
- **Cache tokens** may be counted multiple times (once per cache hit)
- **Agent recording gaps** — some Agents/versions don't record all fields
- **Timezone mismatch** — API dashboards use UTC, this tool uses local time
- **Relay modification** — some relays alter or drop the `usage` field

> This is a **local ledger** — it shows what your Agent recorded, not the upstream billing.
