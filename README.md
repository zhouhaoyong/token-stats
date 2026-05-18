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
| **Token stats** — by time range | `token-stats -b hermes --today` | Multi-agent (Hermes / Claude Code / CodeX / OpenClaw), multi-model. Input/output/cache tokens + call counts, only models with data |
| **Live monitor** — context tracking | `token-stats -b hermes --watch` | Per-round delta + cumulative, warns above 90%. macOS / Linux / Windows |
| **Compare** — side-by-side periods | `--compare --a today --b yesterday` | Any time range, multi-model comparison with diff column |
| **Export** — JSON / CSV | `--export` | Multi-agent, multi-period combinations. Interactive directory picker |
| **Model detect** — proxy API verification | `token-stats -b <name>` | Auto-detects 69 models from 13 providers by actual API response name |

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
# Output: token-stats v2.3.4

# Check 2: list installed agents
token-stats --list-backends
# Example output:
#   ✅ Hermes
#   ✅ Claude Code
#   ❌ CodeX
#   ❌ OpenClaw

# Check 3: view stats for an agent
token-stats -b hermes
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

---

## Common Commands

The ones you'll actually reach for day-to-day:

```bash
# 📊 View all agents (current stats)
token-stats --all

# 📊 View all agents — today only
token-stats --all --today

# 📊 View all agents — this month (e.g. May 2026)
token-stats --all --from 2026-05-01 --to 2026-05-31

# 📤 Export → just add --export (interactive dir/format picker)
token-stats --all --export
token-stats --all --today --export
token-stats --all --from 2026-05-01 --to 2026-05-31 --export

# 🎯 Single agent
token-stats -b hermes
token-stats -b hermes --today
token-stats -b hermes --from 2026-05-01 --to 2026-05-31

# ⚖️ Today vs yesterday
token-stats -b hermes --compare --a today --b yesterday

# 👀 Live context monitor (alerts when context is nearly full)
token-stats -b hermes --watch

# 👀 Pick an agent interactively, then enter watch mode
token-stats --watch
```

> Replace `hermes` with any agent name (`claude-code` / `codex` / `openclaw`).

## Usage

### Quick view

```bash
# Interactive menu
token-stats

# Skip the menu
token-stats -b hermes
token-stats -b claude-code
token-stats -b codex
token-stats -b openclaw

# Multiple agents at once (comma-separated)
token-stats -b hermes,claude-code

# All agents at once
token-stats --all

# Current snapshot (same as default)
token-stats -b hermes --now
```

Output example (one line per model, only models with data):
```
📊 Hermes
  deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 缓存 480.6K | 调用 13 次

📊 Claude Code
  deepseek-v4-pro | 上下文 2.60M/1.05M (>100%) | 输入 1.78M | 输出 823.0K | 缓存 341.48M | 调用 1723 次
  Qwen3-Coder-30B | 上下文 23.0K/131.1K (17.6% ✅) | 输入 22.9K | 输出 131 | 调用 1 次
```

### Time range queries

Shows total tokens in a period (no context %, shows session count):

```bash
# Today
token-stats -b hermes --today

# Yesterday
token-stats -b hermes --yesterday

# This week (Monday to now)
token-stats -b hermes --week

# Last 7 days
token-stats -b hermes --last-7d

# Custom date range (from 00:00:00 to 23:59:59)
token-stats -b hermes --from 2025-01-01 --to 2025-01-31
```

Time range output (no context %, shows session count):
```
📊 Hermes
  deepseek-v4-flash | 总计 988.9K | 输入 660.5K | 输出 327.0K | 缓存 72.66M | 调用 699 次 | 4 轮会话
```

### Compare two time periods

```bash
# Shortcut vs shortcut
token-stats -b hermes --compare --a today --b yesterday
token-stats -b hermes --compare --a this-week --b last-week

# Single day vs single day
token-stats -b hermes --compare --a 2025-01-01 --b 2025-01-15

# Date range vs date range (YYYY-MM-DD~YYYY-MM-DD)
token-stats -b hermes --compare --a 2025-01-01~2025-01-07 --b 2025-01-08~2025-01-14
```

Compare output:
```
📊 对比: "today" vs "yesterday"  [Hermes]
══════════════════════════════════════════════════════════════════════
  模型                           |            A |            B |           变化
──────────────────────────────────────────────────────────────────────
  deepseek-v4-flash            |       988.9K |        65.4K |      -923.5K
──────────────────────────────────────────────────────────────────────
  总计                           |       988.9K |        65.4K |      -923.5K
```

### Export data

Interactive directory + format selection:

```bash
# Export latest session
token-stats -b hermes --export

# Export today's data
token-stats -b hermes --today --export

# Export yesterday's data
token-stats -b hermes --yesterday --export

# Export last 7 days
token-stats -b hermes --last-7d --export

# Export custom date range
token-stats -b hermes --from 2025-01-01 --to 2025-01-31 --export

# Export multiple agents (comma-separated)
token-stats -b hermes,claude-code --export

# Export all installed agents
token-stats --all --export

# Multi-agent + time range (all combinations work)
token-stats -b hermes,claude-code --today --export          # Multiple agents, today only
token-stats --all --today --export                          # All agents, today only
token-stats --all --from 2025-01-01 --to 2025-01-31 --export  # All agents, custom period
token-stats -b hermes,claude-code --yesterday --export      # Multiple agents, yesterday
token-stats -b hermes,claude-code --week --export           # Multiple agents, this week
```

Flow: shows stats → prompts for directory → prompts for JSON or CSV.

**Single agent export shows per-model breakdown + a "Total" row when multiple models exist:**
```text
📊 Hermes — Export (2026-05-18)
════════════════════════════════════════════════════
  deepseek-v4-flash
    context          178.4K /   1.05M (17.0%)
    input tokens     115.1K
    output tokens     63.3K
    cache tokens     18.10M
    calls            192 (today: 24)
    ─────────────────────────────────────
    total tokens     178.4K
    total + cache    18.28M

  claude-sonnet-4
    context           85.5K /  200.0K (42.8%)
    input tokens      52.2K
    output tokens     33.3K
    cache tokens      2.00M
    calls             10 (today: 24)
    ─────────────────────────────────────
    total tokens      85.5K
    total + cache     2.09M

  ──────────────────────────────────────────    ← auto-added for multi-model
  Total
    input tokens     167.3K
    output tokens     96.6K
    cache tokens     20.10M
    calls            202
    ─────────────────────────────────────
    total tokens     263.9K
    total + cache    20.36M
```

**Multi-agent export (`--all --export` or `-b a,b --export`):**
Each agent is shown separately, with a grand total across all agents.
JSON uses an `"agents": [...]` structure; CSV adds an `Agent` column.

Supports all 3 OS path formats:
- macOS/Linux: `~/Desktop`, `/tmp/data`
- Windows: `C:\Users\xxx\Documents`

### Live monitoring

```bash
# Interactive → watch
token-stats --watch

# Direct
token-stats -b hermes --watch
token-stats -b claude-code --watch 2   # 2-second interval
```

Polls every N seconds (default 5). Ctrl+C to stop and see a summary with final state + total delta.

Example output (single model):
```text
── [05:30:45] +347 tokens (+1 calls) ──
  deepseek-v4-flash | context 119.2K/1.05M (11.4% ✅) | input +333/82.6K tokens | output +14/36.6K tokens | cache +103.0K/7.93M tokens | calls +1/115
  deepseek-v4-flash | input 480.0K tokens | output 120.0K tokens | total 600.0K tokens | cache 8.50M tokens | calls 22       ← today totals

── [05:30:50] no change ──                                     ← single line only when nothing changed
```

Example output (multiple models, per-model today totals + total row):
```text
── [05:30:55] +1.2K tokens (+2 calls) ──
  deepseek-v4-flash | context 178.4K/1.05M (17.0% ✅) | input +968/115.1K tokens | output +232/63.3K tokens | ...
  claude-sonnet-4    | context 85.5K/200K (42.8%) | input +87/52.2K tokens | output +40/33.2K tokens | ...
  deepseek-v4-flash | input 481.2K tokens | output 120.2K tokens | total 601.4K tokens | cache 8.81M tokens | calls 24
  claude-sonnet-4   | input 200.1K tokens | output 50.1K tokens | total 250.2K tokens | cache 2.01M tokens | calls 11
  ──────────────────────────────────────────────────────────────────────────────────────────────────
  Total             | input 681.3K tokens | output 170.3K tokens | total 851.6K tokens | cache 10.82M tokens | calls 35
```

**What live monitoring tells you:**
- Current context window occupancy (`context 119.2K/1.05M (11.4% ✅)`) — how full is your session?
- Per-round **input/output/cache** delta and cumulative
- **Model calls: delta / window total**
- Whether the context window is nearly full (>90% 🚨), before the model silently drops older messages
- Summary of total consumption during the monitoring session

**Why this matters if you never start a fresh session:**

Running without ever starting a fresh session won't crash the model, but has three real costs:

1. **Cost per round skyrockets** — at 800K context each round sends ~800K input tokens; 10 rounds can cost $1+. After a fresh session, each round sends just a few K — nearly free
2. **Response gets slower** — processing 1M context is much slower than 100K; you'll feel the delay before the first character appears
3. **Model silently forgets** — past the context limit, the oldest messages are quietly dropped with **zero warning**. Ask "remember what we said earlier?" and the model may confidently fabricate an answer

> 💡 **Recommended strategy**:
> - Above **60%** → type `/compact` (compresses context, faster than `/new`, retains key info)
> - Above **90%** → type `/new` (clears context, starts fresh)
>
> These commands work **across all platforms** (CLI, IDE plugins, chat apps like QQ/DingTalk all support slash commands).
> IDE plugins also provide toolbar buttons ("Compact" / "New Chat") with the same effect.
>
> Carry key info (preferences, project structure, config) via memory or notes — don't rely on context alone.

### See what's installed

```bash
token-stats --list-backends
```

✅ = installed, ❌ = not found. Missing agents won't appear in the menu.

---

## Command Reference

All commands accept `-b <name>` where `<name>` can be: `hermes`, `claude-code`, `codex`, `openclaw`.

### Basics

| Command | Description |
|---------|-------------|
| `token-stats` | Interactive menu → pick an agent → view stats |
| `token-stats -b <name>` | Skip the menu, pick an agent directly |
| `token-stats --version` | Show version number |
| `token-stats -b <name> --detail` | Detailed mode (same as default) |
| `token-stats -b <name> --now` | Current snapshot (same as default) |

### Time Ranges

| Command | Description |
|---------|-------------|
| `token-stats -b <name> --today` | Today's stats (00:00:00 ~ now) |
| `token-stats -b <name> --yesterday` | Yesterday's stats (all day) |
| `token-stats -b <name> --week` | This week (Monday till now) |
| `token-stats -b <name> --last-7d` | Last 7 days |
| `token-stats -b <name> --from 2025-01-01 --to 2025-01-31` | Custom range (start 00:00 ~ end 23:59) |

### Comparison

| Command | Description |
|---------|-------------|
| `token-stats -b <name> --compare --a today --b yesterday` | Quick label comparison |
| `token-stats -b <name> --compare --a this-week --b last-week` | This week vs last week |
| `token-stats -b <name> --compare --a 2025-01-01 --b 2025-01-15` | Two single-day comparison |
| `token-stats -b <name> --compare --a 2025-01-01~2025-01-07 --b 2025-01-08~2025-01-14` | Custom date range comparison |

**`--a` / `--b` supported formats:**
- `today`, `yesterday`
- `this-week`, `last-week`
- `YYYY-MM-DD` — single day
- `YYYY-MM-DD~YYYY-MM-DD` — date range

### Export

| Command | Description |
|---------|-------------|
| `token-stats -b <name> --export` | Export current stats (interactive directory + format) |
| `token-stats -b <name> --today --export` | Export today's stats |
| `token-stats -b <name> --yesterday --export` | Export yesterday's stats |
| `token-stats -b <name> --last-7d --export` | Export last 7 days |
| `token-stats -b <name> --from X --to Y --export` | Export custom date range |
| `token-stats -b <name1>,<name2> --export` | Export multiple agents (comma-separated) |
| `token-stats --all --export` | Export all installed agents |

### Live Monitoring

| Command | Description |
|---------|-------------|
| `token-stats --watch` | Interactive → monitor, polls every 5s (Ctrl+C to stop) |
| `token-stats -b <name> --watch` | Direct agent, default 5s interval |
| `token-stats -b <name> --watch 10` | Custom 10s interval |

### Multi-Agent

| Command | Description |
|---------|-------------|
| `token-stats --all` | Show stats for ALL installed agents |
| `token-stats -b <name1>,<name2>` | Show multiple agents at once (comma-separated) |
| `token-stats --all --export` | Export stats for all agents |
| `token-stats --list-backends` | List installed agents (check mark or cross) |

### Setup & Maintenance

| Command | Description |
|---------|-------------|
| `clawhub install agent-usage-stats` | Install from ClawHub |
| `token-stats --setup` | Create global command + auto-add to PATH |
| `token-stats --uninstall` | Remove global command + auto-clean PATH |

> 💡 All commands above are also available via `token-stats --help`.

---

## What each agent shows

Output always starts with `📊 Agent Name`, followed by one line per **model with data** (unused models are hidden).

| Agent | What you see |
|-------|-------------|
| **Hermes** | Model, context usage (with % + recommendation), input/output/cache tokens, API calls, session count |
| **Claude Code** | Per-model context usage, calls, sub-agent count, total sessions/projects |
| **CodeX** | Per-model thread count (tokens may be 0, shows session count only) |
| **OpenClaw** | Model (with provider), context usage %, input/output tokens, agent count |

### Data sources (for troubleshooting)

| Agent | Reads from |
|-------|-----------|
| Hermes | `~/.hermes/state.db` → sessions table |
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| CodeX | `~/.codex/state_*.sqlite` → threads table |
| OpenClaw | `~/.openclaw/agents/main/sessions/sessions.json` |

### Windows + WSL2

When your agent runs inside WSL2, `token-stats` automatically detects and reads data from the Windows side. Even if Hermes is running (database locked), it reads via `wsl.exe` internally; output is labeled `(WSL)`.

1. **WSL distro must be running** — open a WSL terminal first
2. **Username agnostic** — auto-detects the WSL user's home directory, independent of Windows login
3. **Proxy unaffected** — VPN/proxy only affects WSL networking, not local file access

### Supported Models (69 models, 13 providers)

`token-stats` detects your model and displays the correct context window size. Unknown models default to 128K.

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

Prefix matching is supported: `claude-opus-4-7-20250219` → 200K, `gpt-4.1-preview` → 1M, `deepseek-v4-0324` → 1M.

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
token-stats -b hermes --export
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

### API Relay / Proxy Service

> If you access LLMs through an **API relay (中转站)**, note the following caveats.

token-stats relies on the `usage` object returned by the real API. The data flow is:

```
Your Agent → Relay → Real API
                         ↓
           Real API returns usage object
                         ↓
           Relay forwards the response to your Agent
                         ↓
           Your Agent writes to local storage
                         ↓
           token-stats reads from local storage
```

**Accurate stats require:** the relay to pass through the original API response **as-is** (including the `usage` field). Most mainstream relays do this.

**Stats may be inaccurate if:** the relay:
- Removes the `usage` field
- Tampers with token counts (e.g. inflating usage)
- Replaces model names

token-stats **only records what it receives** — it does not verify data against the real API. It is a **local ledger** that records what your Agent wrote down, not the upstream API's billing invoice.

> If you suspect relay data is inaccurate, compare token-stats output with the relay's billing dashboard. Discrepancies suggest data may have been modified.

---

token-stats is fundamentally an **open-source transparency tool**. It does not judge relay services — it makes token consumption **auditable and verifiable**:

- For **honest relays**: users can cross-check and build trust
- For **dishonest relays**: data discrepancies expose the problem

Whether you connect directly or through a relay, users deserve to know their actual consumption. token-stats doesn't take sides — it just keeps the books.
