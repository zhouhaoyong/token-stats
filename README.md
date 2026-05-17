<p align="center">
  <a href="README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="README.zh.md"><strong>🇨🇳 简体中文</strong></a>
</p>

# token-stats

> Pick an AI assistant → see how many tokens it's burning.

## What's this?

You have multiple AI assistants installed on your machine (Hermes, Claude Code, CodeX…).
`token-stats` lets you **choose one and see its token consumption** — every time you run it.

## Install

```bash
# Step 1: Install from ClawHub
clawhub install agent-usage-stats

# Step 2: Create global command (script may lack +x, so prefix with python3)
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

That's it. Now just type `token-stats` in your terminal.

## Usage

### Interactive (default)

```bash
token-stats
```

Shows a menu like this:

```
🔍 选择你要监控的 AI 助手：
────────────────────────────────────────
  [1] Hermes
  [2] Claude Code
  [3] CodeX
  [q] 退出
────────────────────────────────────────
请选择 (1-3)：
```

Pick one, see its stats. **You choose every time.**

### Skip the menu

```bash
token-stats -b hermes
token-stats -b claude-code
token-stats -b codex
```

### Live monitoring

```bash
token-stats --watch
```

Pick an agent, then the script polls every 5 seconds showing live token growth.
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

## What each agent shows

| Agent | What you see |
|-------|-------------|
| **Hermes** | Current session: model, context usage %, API calls, tool calls, input/output/cache tokens |
| **Claude Code** | All projects aggregate: calls, sub-agent calls, input/output/cache tokens |
| **CodeX** | Total tokens from database, thread count |
| **OpenClaw** | All sessions aggregate: tokens, current model |

## Supported platforms

- ✅ macOS / Linux
- ✅ Python 3.8+
- ✅ Pure Python stdlib, zero dependencies
- ⬜ Windows (coming soon)

## Uninstall

```bash
clawhub uninstall agent-usage-stats
rm -f ~/.local/bin/token-stats
```
