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

### Interactive Menu

```bash
token-stats                           # interactive picker
token-stats -a hermes                 # skip menu, go straight to Hermes
token-stats -a hermes,claude-code     # multiple agents
token-stats --all                     # all agents at once
```

### Snapshot & Time Ranges

```bash
# Current snapshot (default)
token-stats -a hermes

# Quick time ranges
token-stats -a hermes --today         # today
token-stats -a hermes --yesterday     # yesterday
token-stats -a hermes --week          # this week (from Monday)
token-stats -a hermes --last-7d       # last 7 days
token-stats -a hermes --month         # this month
token-stats -a hermes --year          # this year

# Custom range
token-stats -a hermes --from 2026-01-01 --to 2026-05-18
```

Snapshot output:
```
📊 Hermes
  deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 缓存 480.6K | 调用 13 次

📊 Claude Code
  deepseek-v4-pro | 总计/+缓存 11.83M/2.07G | 输入 8.07M | 输出 3.76M | 调用 8274 次
```

### Live Monitor

Watch token consumption in real time while using your agent:

```bash
token-stats -a hermes --watch         # refresh every 5s (default)
token-stats -a claude-code --watch 2  # refresh every 2s
```

- Context > 60% → suggests `/compact`; > 90% → warning
- `Ctrl+C` to stop and see a monitoring summary

### Compare

Side-by-side comparison of two time periods with diff columns:

```bash
# Quick label comparison
token-stats -a hermes --compare --a today --b yesterday
token-stats -a hermes --compare --a this-week --b last-week

# Custom date comparison
token-stats -a hermes --compare --a 2026-01-01 --b 2026-01-15

# Date range comparison
token-stats -a hermes --compare --a 2026-01-01~2026-01-07 --b 2026-01-08~2026-01-14
```

Compare labels: `today`, `yesterday`, `this-week`, `last-week`, `this-month`, `last-month`, `this-year`, `last-year`, `YYYY-MM-DD`, `YYYY-MM-DD~YYYY-MM-DD`

### Export

Interactive directory and format picker (XLSX / JSON):

```bash
# Basic export
token-stats -a hermes --export

# Export with time range
token-stats -a hermes --today --export
token-stats -a hermes --month --export
token-stats -a hermes --year --export

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
