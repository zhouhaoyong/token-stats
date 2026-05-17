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

With plenty of log viewers out there, why pick this one?

| What you want to do | How | What it solves |
|---------------------|-----|----------------|
| **📊 Check the bill** — one look at your spend | `token-stats` | All agents, all models, one line each. Only models with data show up — no noise |
| **📡 Watch it live** — see context fill up in real time | `token-stats -b hermes --watch` | Per-round delta + current context ratio. Alerts before things get tight, tells you when to `/new` |
| **📅 Compare periods** — did today burn more than yesterday? | `--today --compare --a today --b yesterday` | Any time range aggregation, side-by-side comparison with diff. Trends at a glance |
| **💾 Export** — save stats for records | `--export` | Interactive directory + format selection (JSON/CSV). Cross-platform paths |

**Zero dependencies** — pure Python stdlib, no pip install needed. macOS / Linux supported.

---

## Environment Requirements

Before installing `token-stats`, make sure you have these:

### 1. Python 3.8+

`token-stats` is a pure Python script using only stdlib — no pip packages needed.

```bash
# Check
python3 --version

# If missing → https://www.python.org/downloads/
# macOS usually ships with Python 3. Windows needs a manual install.
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
clawhub --version   # should show v0.9.x
```

> 💡 On macOS with Homebrew-installed Node.js, `npm install -g clawhub` puts it at `/opt/homebrew/bin/clawhub`, which is usually already in your PATH.

> 💡 If you're in China and npm is slow, use the npmmirror registry:
> ```bash
> npm install -g clawhub --registry=https://registry.npmmirror.com
> ```

---

## Install

```bash
# Step 1: Install from ClawHub
clawhub install agent-usage-stats

# Step 2: Create the global command (setup writes a shell wrapper, no +x needed)
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

That's it. Now just type `token-stats` in your terminal.

### Verify Installation

```bash
# Check 1: version
token-stats --version
# Output: token-stats v2.1.1

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
# Pull the latest version from ClawHub
clawhub update agent-usage-stats

# Re-run setup (needed if the script changed)
python3 ~/skills/agent-usage-stats/token-stats.py setup

# Verify version
token-stats --version
```

> 💡 It's recommended to re-run `setup` after every update so the global command stays current.
> If `clawhub update` doesn't change the version, use `--force`:
> ```bash
> clawhub install agent-usage-stats --force
> ```

> ⚠️ ClawHub installs skills into a `skills/` folder under your **current working directory**.
> Run `clawhub install` from `~` or `~/.hermes/` to keep things tidy.

---

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

**Why this matters if you never `/new`:**

Running without ever starting a fresh session won't crash the model, but has three real costs:

1. **Cost per round skyrockets** — at 800K context each round sends ~800K input tokens; 10 rounds can cost $1+. After `/new`, each round sends just a few K — nearly free
2. **Response gets slower** — processing 1M context is much slower than 100K; you'll feel the delay before the first character appears
3. **Model silently forgets** — past the context limit, the oldest messages are quietly dropped with **zero warning**. Ask "remember what we said earlier?" and the model may confidently fabricate an answer

> 💡 **Recommended strategy**: consider `/new` when context exceeds **60%**, strongly recommended above **90%**. Carry key info (preferences, project structure, config) via memory or notes into the fresh session.

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
| `token-stats --setup` | Create global command at `~/.local/bin/token-stats` |

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
| OpenClaw | `~/ai-testing-lab/openclaw/data/agents/main/sessions/sessions.json` |

---

## Uninstall

```bash
clawhub uninstall agent-usage-stats
rm -f ~/.local/bin/token-stats

# Clean up old aliases (if you previously set alias token-stats=...)
grep "alias token-stats" ~/.zshrc ~/.bashrc 2>/dev/null || echo "No old aliases found"

# If any found, remove them:
sed -i '' '/alias token-stats/d' ~/.zshrc
source ~/.zshrc
```

---

## Compatibility

| Platform | Status |
|----------|--------|
| macOS | ✅ Full support |
| Linux | ✅ Full support |
| Windows | ⬜ Planned (PRs welcome) |

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

#### ❓ `python3 ~/skills/agent-usage-stats/token-stats.py setup` says file not found

**Cause: ClawHub installed skills in a different directory than `~/skills/`.**

```bash
# Find where token-stats.py actually is
find ~ -name "token-stats.py" -type f 2>/dev/null

# Once found, cd to that directory and setup from there, or reinstall from ~:
cd ~
clawhub install agent-usage-stats
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

#### ❓ `token-stats` command not found

**Cause: `~/.local/bin/` is not in PATH.**

```bash
# Check
echo $PATH | grep .local/bin

# If empty, add it:
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc
source ~/.zshrc

# Or run directly
~/.local/bin/token-stats --version
```

#### ❓ `Permission denied` when running `token-stats`

**Cause: wrapper script lacks execute permission.**

```bash
chmod +x ~/.local/bin/token-stats
# Or just re-run setup
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

### Runtime issues

#### ❓ My agent isn't showing in the menu

**Cause: `token-stats` checks for specific config files.** These paths must exist:

| Agent | Detection path |
|-------|---------------|
| **Hermes** | `~/.hermes/state.db` |
| **Claude Code** | `~/.claude/projects/` |
| **CodeX** | `~/.codex/state_*.sqlite` |
| **OpenClaw** | `~/ai-testing-lab/openclaw/data/agents/main/sessions/sessions.json` |

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

#### ❓ Export says "directory not found"

**Cause: the directory path you entered doesn't exist.** Create it first:

```bash
mkdir -p ~/Desktop/my-data
token-stats -b hermes --export
# Enter: ~/Desktop/my-data
```

#### ❓ `--compare` shows no data for both periods

**Possible cause:** neither period has session records. Check with `--today` first.

### Data scope

> ⚠️ `token-stats` **only reads local agent data from this machine**.
>
> - If you run Hermes on PC A and Claude Code on PC B, each machine stores and reports its own data
> - `token-stats` reads disk files, not cloud APIs
> - To see stats on another machine, install `token-stats` there too
> - All statistics are per-agent, not a cross-agent total
