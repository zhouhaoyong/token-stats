# token-stats — Pick an Agent, See Its Token Burn

Run it, pick an agent, see the stats. Every time.

## What's this?

You have multiple AI assistants on your machine (Hermes, Claude Code, CodeX, OpenClaw…).
`token-stats` lets you **choose one and see how many tokens it's consuming**.

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

---

## Install

```bash
# Step 1: Install from ClawHub
clawhub install agent-usage-stats

# Step 2: Create the global command (setup writes a shell wrapper, no +x needed)
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

That's it. Now just type `token-stats` in your terminal.

> ⚠️ ClawHub installs skills into a `skills/` folder under your **current working directory**.
> Run `clawhub install` from `~` or `~/.hermes/` to keep things tidy.

---

## Usage

### Interactive (default)

```bash
token-stats
```

Shows a menu:
```
🔍 选择你要监控的 AI 助手：
────────────────────────────────────────
  [1] Hermes
  [2] Claude Code
  [3] CodeX
  [4] OpenClaw
  [q] 退出
────────────────────────────────────────
请选择 (1-4)：
```

Pick one, see its stats. **You choose every time.**

### Skip the menu

```bash
token-stats -b hermes
token-stats -b claude-code
token-stats -b codex
token-stats -b openclaw
```

### Live monitoring

```bash
token-stats --watch
```

Pick an agent → polls every 5 seconds showing live token growth.
Hit `Ctrl+C` to stop.

Or skip the menu:

```bash
token-stats -b hermes --watch
token-stats -b claude-code --watch 2    # poll every 2 seconds
```

### See what's installed

```bash
token-stats --list-backends
```

✅ = installed, ❌ = not found. Missing agents won't appear in the menu.

---

## What each agent shows

| Agent | What you see |
|-------|-------------|
| **Hermes** | Model, context usage (with % + recommendation), API calls, tool calls, input/output/cache tokens, session count |
| **Claude Code** | Aggregate across projects: calls, sub-agent calls, input/output/cache tokens |
| **CodeX** | Total tokens from database, thread count |
| **OpenClaw** | Model (with provider), context usage %, input/output/cache tokens |

### Data sources (for troubleshooting)

| Agent | Reads from |
|-------|-----------|
| Hermes | `~/.hermes/state.db` → sessions table |
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| CodeX | `~/.codex/state_*.sqlite` → threads table |
| OpenClaw | `~/ai-testing-lab/openclaw/data/.../sessions.json` |

---

## Uninstall

```bash
clawhub uninstall agent-usage-stats
rm -f ~/.local/bin/token-stats
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

## FAQ

### ❓ `python3 ~/skills/…/token-stats.py setup` says file not found

ClawHub installs skills into `skills/` under your **current working directory** (not `~`).
Check if `~/skills/` exists, or reinstall from your home directory:

```bash
cd ~
clawhub install agent-usage-stats
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

### ❓ `token-stats` command not found

Make sure `~/.local/bin/` is in your PATH:

```bash
echo $PATH | grep .local/bin
# If empty, add it:
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc
source ~/.zshrc
```

### ❓ `clawhub install` fails

Check Node.js version and network:

```bash
node --version   # needs v18+
npm install -g clawhub  # reinstall
```

### ❓ My agent isn't showing in the menu

`token-stats` checks for config files. Run `token-stats --list-backends` to see what's detected.
Missing agents require:
- **Hermes**: `~/.hermes/state.db`
- **Claude Code**: `~/.claude/projects/`
- **CodeX**: `~/.codex/state_*.sqlite`
- **OpenClaw**: `~/ai-testing-lab/openclaw/data/.../sessions.json`
