     1|# token-stats — Pick an Agent, See Its Token Burn
     2|
     3|Run it, pick an agent, see the stats. Every time.
     4|
     5|## What's this?
     6|
     7|You have multiple AI assistants on your machine (Hermes, Claude Code, CodeX, OpenClaw…).
     8|`token-stats` lets you **choose one and see how many tokens it's consuming**.
     9|
    10|> ⚠️ **Important: this tool only reads local agent data on this machine.**
    11|> If you run agents on different PCs or servers, each machine stores its own data
    12|> and needs its own installation of `token-stats`. Cross-machine statistics are not supported.
    13|>
    14|> All statistics are queried based on the specific agent you select, not a global total.
    15|
    16|---
    17|
    18|## Environment Requirements
    19|
    20|Before installing `token-stats`, make sure you have these:
    21|
    22|### 1. Python 3.8+
    23|
    24|`token-stats` is a pure Python script using only stdlib — no pip packages needed.
    25|
    26|```bash
    27|# Check
    28|python3 --version
    29|
    30|# If missing → https://www.python.org/downloads/
    31|# macOS usually ships with Python 3. Windows needs a manual install.
    32|```
    33|
    34|### 2. Node.js (needed for the installer)
    35|
    36|`token-stats` is distributed via **ClawHub CLI**, a Node.js command-line tool.
    37|
    38|```bash
    39|# Check
    40|node --version
    41|
    42|# If missing → https://nodejs.org (get the LTS version)
    43|```
    44|
    45|Node.js includes `npm`, which is used to install ClawHub.
    46|
    47|### 3. ClawHub CLI
    48|
    49|```bash
    50|# Install
    51|npm install -g clawhub
    52|
    53|# Verify
    54|clawhub --version   # should show v0.9.x
    55|```
    56|
    57|> 💡 On macOS with Homebrew-installed Node.js, `npm install -g clawhub` puts it at `/opt/homebrew/bin/clawhub`, which is usually already in your PATH.
    58|
    59|> 💡 If you're in China and npm is slow, use the npmmirror registry:
    60|> ```bash
    61|> npm install -g clawhub --registry=https://registry.npmmirror.com
    62|> ```
    63|
    64|---
    65|
    66|## Install
    67|
    68|```bash
    69|# Step 1: Install from ClawHub
    70|clawhub install agent-usage-stats
    71|
    72|# Step 2: Create the global command (setup writes a shell wrapper, no +x needed)
    73|python3 ~/skills/agent-usage-stats/token-stats.py setup
    74|```
    75|
    76|That's it. Now just type `token-stats` in your terminal.
    77|
    78|### Verify Installation
    79|
    80|```bash
    81|# Check 1: version
    82|token-stats --version
    83|# Output: token-stats v2.0.7
    84|
    85|# Check 2: list installed agents
    86|token-stats --list-backends
    87|# Example output:
    88|#   ✅ Hermes
    89|#   ✅ Claude Code
    90|#   ❌ CodeX
    91|#   ❌ OpenClaw
    92|
    93|# Check 3: view stats for an agent
    94|token-stats -b hermes
    95|# Example output:
    96|# 📊 Hermes
    97|#   deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 调用 13 次
    98|```
    99|
   100|If all three checks produce output, installation is successful 🎉
   101|
   102|> ⚠️ ClawHub installs skills into a `skills/` folder under your **current working directory**.
   103|> Run `clawhub install` from `~` or `~/.hermes/` to keep things tidy.
   104|
   105|---
   106|
   107|## Usage
   108|
   109|### Quick view
   110|
   111|```bash
   112|# Interactive menu
   113|token-stats
   114|
   115|# Skip the menu
   116|token-stats -b hermes
   117|token-stats -b claude-code
   118|token-stats -b codex
   119|token-stats -b openclaw
   120|
   121|# All agents at once
   122|token-stats --all
   123|
   124|# Current snapshot (same as default)
   125|token-stats -b hermes --now
   126|```
   127|
   128|Output example (one line per model, only models with data):
   129|```
   130|📊 Hermes
   131|  deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 缓存 480.6K | 调用 13 次
   132|
   133|📊 Claude Code
   134|  deepseek-v4-pro | 上下文 2.60M/1.05M (>100%) | 输入 1.78M | 输出 823.0K | 缓存 341.48M | 调用 1723 次
   135|  Qwen3-Coder-30B | 上下文 23.0K/131.1K (17.6% ✅) | 输入 22.9K | 输出 131 | 调用 1 次
   136|```
   137|
   138|### Time range queries
   139|
   140|Shows total tokens in a period (no context %, shows session count):
   141|
   142|```bash
   143|# Today
   144|token-stats -b hermes --today
   145|
   146|# Yesterday
   147|token-stats -b hermes --yesterday
   148|
   149|# This week (Monday to now)
   150|token-stats -b hermes --week
   151|
   152|# Last 7 days
   153|token-stats -b hermes --last-7d
   154|
   155|# Custom date range (from 00:00:00 to 23:59:59)
   156|token-stats -b hermes --from 2025-01-01 --to 2025-01-31
   157|```
   158|
   159|Time range output (no context %, shows session count):
   160|```
   161|📊 Hermes
   162|  deepseek-v4-flash | 总计 988.9K | 输入 660.5K | 输出 327.0K | 缓存 72.66M | 调用 699 次 | 4 轮会话
   163|```
   164|
   165|### Compare two time periods
   166|
   167|```bash
   168|# Shortcut vs shortcut
   169|token-stats -b hermes --compare --a today --b yesterday
   170|token-stats -b hermes --compare --a this-week --b last-week
   171|
   172|# Single day vs single day
   173|token-stats -b hermes --compare --a 2025-01-01 --b 2025-01-15
   174|
   175|# Date range vs date range (YYYY-MM-DD~YYYY-MM-DD)
   176|token-stats -b hermes --compare --a 2025-01-01~2025-01-07 --b 2025-01-08~2025-01-14
   177|```
   178|
   179|Compare output:
   180|```
   181|📊 对比: "today" vs "yesterday"  [Hermes]
   182|══════════════════════════════════════════════════════════════════════
   183|  模型                           |            A |            B |           变化
   184|──────────────────────────────────────────────────────────────────────
   185|  deepseek-v4-flash            |       988.9K |        65.4K |      -923.5K
   186|──────────────────────────────────────────────────────────────────────
   187|  总计                           |       988.9K |        65.4K |      -923.5K
   188|```
   189|
   190|### Export data
   191|
   192|Interactive directory + format selection:
   193|
   194|```bash
   195|# Export latest session
   196|token-stats -b hermes --export
   197|
   198|# Export today's data
   199|token-stats -b hermes --today --export
   200|
   201|# Export yesterday's data
   202|token-stats -b hermes --yesterday --export
   203|
   204|# Export last 7 days
   205|token-stats -b hermes --last-7d --export
   206|
   207|# Export custom date range
   208|token-stats -b hermes --from 2025-01-01 --to 2025-01-31 --export
   209|```
   210|
   211|Flow: shows stats → prompts for directory → prompts for JSON or CSV.
   212|
   213|Supports all 3 OS path formats:
   214|- macOS/Linux: `~/Desktop`, `/tmp/data`
   215|- Windows: `C:\Users\xxx\Documents`
   216|
   217|### Live monitoring
   218|
   219|```bash
   220|# Interactive → watch
   221|token-stats --watch
   222|
   223|# Direct
   224|token-stats -b hermes --watch
   225|token-stats -b claude-code --watch 2   # 2-second interval
   226|```
   227|
   228|Polls every 5 seconds (configurable). Ctrl+C to stop and see a summary table.
   229|
   230|### See what's installed
   231|
   232|```bash
   233|token-stats --list-backends
   234|```
   235|
   236|✅ = installed, ❌ = not found. Missing agents won't appear in the menu.
   237|
   238|---
   239|
   240|## Command Reference
   241|
   242|All commands accept `-b <name>` where `<name>` can be: `hermes`, `claude-code`, `codex`, `openclaw`.
   243|
   244|### Basics
   245|
   246|| Command | Description |
   247||---------|-------------|
   248|| `token-stats` | Interactive menu → pick an agent → view stats |
   249|| `token-stats -b <name>` | Skip the menu, pick an agent directly |
   250|| `token-stats --version` | Show version number |
   251|| `token-stats -b <name> --detail` | Detailed mode (same as default) |
   252|| `token-stats -b <name> --now` | Current snapshot (same as default) |
   253|
   254|### Time Ranges
   255|
   256|| Command | Description |
   257||---------|-------------|
   258|| `token-stats -b <name> --today` | Today's stats (00:00:00 ~ now) |
   259|| `token-stats -b <name> --yesterday` | Yesterday's stats (all day) |
   260|| `token-stats -b <name> --week` | This week (Monday till now) |
   261|| `token-stats -b <name> --last-7d` | Last 7 days |
   262|| `token-stats -b <name> --from 2025-01-01 --to 2025-01-31` | Custom range (start 00:00 ~ end 23:59) |
   263|
   264|### Comparison
   265|
   266|| Command | Description |
   267||---------|-------------|
   268|| `token-stats -b <name> --compare --a today --b yesterday` | Quick label comparison |
   269|| `token-stats -b <name> --compare --a this-week --b last-week` | This week vs last week |
   270|| `token-stats -b <name> --compare --a 2025-01-01 --b 2025-01-15` | Two single-day comparison |
   271|| `token-stats -b <name> --compare --a 2025-01-01~2025-01-07 --b 2025-01-08~2025-01-14` | Custom date range comparison |
   272|
   273|**`--a` / `--b` supported formats:**
   274|- `today`, `yesterday`
   275|- `this-week`, `last-week`
   276|- `YYYY-MM-DD` — single day
   277|- `YYYY-MM-DD~YYYY-MM-DD` — date range
   278|
   279|### Export
   280|
   281|| Command | Description |
   282||---------|-------------|
   283|| `token-stats -b <name> --export` | Export current stats (interactive directory + format) |
   284|| `token-stats -b <name> --today --export` | Export today's stats |
   285|| `token-stats -b <name> --yesterday --export` | Export yesterday's stats |
   286|| `token-stats -b <name> --last-7d --export` | Export last 7 days |
   287|| `token-stats -b <name> --from X --to Y --export` | Export custom date range |
   288|
   289|### Live Monitoring
   290|
   291|| Command | Description |
   292||---------|-------------|
   293|| `token-stats --watch` | Interactive → monitor, polls every 5s (Ctrl+C to stop) |
   294|| `token-stats -b <name> --watch` | Direct agent, default 5s interval |
   295|| `token-stats -b <name> --watch 10` | Custom 10s interval |
   296|
   297|### Multi-Agent
   298|
   299|| Command | Description |
   300||---------|-------------|
   301|| `token-stats --all` | Show stats for ALL installed agents |
   302|| `token-stats --list-backends` | List installed agents (check mark or cross) |
   303|
   304|### Setup & Maintenance
   305|
   306|| Command | Description |
   307||---------|-------------|
   308|| `clawhub install agent-usage-stats` | Install from ClawHub |
   309|| `token-stats --setup` | Create global command at `~/.local/bin/token-stats` |
   310|
   311|> 💡 All commands above are also available via `token-stats --help`.
   312|
   313|---
   314|
   315|## What each agent shows
   316|
   317|Output always starts with `📊 Agent Name`, followed by one line per **model with data** (unused models are hidden).
   318|
   319|| Agent | What you see |
   320||-------|-------------|
   321|| **Hermes** | Model, context usage (with % + recommendation), input/output/cache tokens, API calls, session count |
   322|| **Claude Code** | Per-model context usage, calls, sub-agent count, total sessions/projects |
   323|| **CodeX** | Per-model thread count (tokens may be 0, shows session count only) |
   324|| **OpenClaw** | Model (with provider), context usage %, input/output tokens, agent count |
   325|
   326|### Data sources (for troubleshooting)
   327|
   328|| Agent | Reads from |
   329||-------|-----------|
   330|| Hermes | `~/.hermes/state.db` → sessions table |
   331|| Claude Code | `~/.claude/projects/**/*.jsonl` |
   332|| CodeX | `~/.codex/state_*.sqlite` → threads table |
   333|| OpenClaw | `~/ai-testing-lab/openclaw/data/agents/main/sessions/sessions.json` |
   334|
   335|---
   336|
   337|## Uninstall
   338|
   339|```bash
   340|clawhub uninstall agent-usage-stats
   341|rm -f ~/.local/bin/token-stats
   342|
   343|# Clean up old aliases (if you previously set alias token-stats=...)
   344|grep "alias token-stats" ~/.zshrc ~/.bashrc 2>/dev/null || echo "No old aliases found"
   345|
   346|# If any found, remove them:
   347|sed -i '' '/alias token-stats/d' ~/.zshrc
   348|source ~/.zshrc
   349|```
   350|
   351|---
   352|
   353|## Compatibility
   354|
   355|| Platform | Status |
   356||----------|--------|
   357|| macOS | ✅ Full support |
   358|| Linux | ✅ Full support |
   359|| Windows | ⬜ Planned (PRs welcome) |
   360|
   361|| Requirement | Details |
   362||-------------|---------|
   363|| Python | 3.8+ (stdlib only, no pip dependencies) |
   364|| Node.js | Required only for installation (ClawHub CLI) |
   365|
   366|---
   367|
   368|## Troubleshooting
   369|
   370|### Installation issues
   371|
   372|#### ❓ `clawhub install agent-usage-stats` fails
   373|
   374|**Possible cause: network issue or outdated Node.js.**
   375|
   376|```bash
   377|# Check Node.js version (needs v18+)
   378|node --version
   379|
   380|# Reinstall ClawHub
   381|npm install -g clawhub
   382|
   383|# In China with slow network:
   384|npm install -g clawhub --registry=https://registry.npmmirror.com
   385|```
   386|
   387|#### ❓ `python3 ~/skills/agent-usage-stats/token-stats.py setup` says file not found
   388|
   389|**Cause: ClawHub installed skills in a different directory than `~/skills/`.**
   390|
   391|```bash
   392|# Find where token-stats.py actually is
   393|find ~ -name "token-stats.py" -type f 2>/dev/null
   394|
   395|# Once found, cd to that directory and setup from there, or reinstall from ~:
   396|cd ~
   397|clawhub install agent-usage-stats
   398|python3 ~/skills/agent-usage-stats/token-stats.py setup
   399|```
   400|
   401|#### ❓ `token-stats` command not found
   402|
   403|**Cause: `~/.local/bin/` is not in PATH.**
   404|
   405|```bash
   406|# Check
   407|echo $PATH | grep .local/bin
   408|
   409|# If empty, add it:
   410|echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc
   411|source ~/.zshrc
   412|
   413|# Or run directly
   414|~/.local/bin/token-stats --version
   415|```
   416|
   417|#### ❓ `Permission denied` when running `token-stats`
   418|
   419|**Cause: wrapper script lacks execute permission.**
   420|
   421|```bash
   422|chmod +x ~/.local/bin/token-stats
   423|# Or just re-run setup
   424|python3 ~/skills/agent-usage-stats/token-stats.py setup
   425|```
   426|
   427|### Runtime issues
   428|
   429|#### ❓ My agent isn't showing in the menu
   430|
   431|**Cause: `token-stats` checks for specific config files.** These paths must exist:
   432|
   433|| Agent | Detection path |
   434||-------|---------------|
   435|| **Hermes** | `~/.hermes/state.db` |
   436|| **Claude Code** | `~/.claude/projects/` |
   437|| **CodeX** | `~/.codex/state_*.sqlite` |
   438|| **OpenClaw** | `~/ai-testing-lab/openclaw/data/agents/main/sessions/sessions.json` |
   439|
   440|Run `token-stats --list-backends` to see what's detected.
   441|
   442|#### ❓ Stats show "no data" or all zeros
   443|
   444|**Possible causes:**
   445|
   446|1. **Agent is installed but never used** → use it first, then check again
   447|2. **Data file path is wrong** → confirm with `token-stats --list-backends`
   448|3. **Time range has no data** → if using `--today` or `--from`, check that sessions exist in that period
   449|
   450|#### ❓ `unknown` model appears in compare results
   451|
   452|**Hermes DB has sessions with empty model field** — doesn't affect accuracy. Diagnose with:
   453|
   454|```bash
   455|sqlite3 ~/.hermes/state.db "SELECT DISTINCT model FROM sessions WHERE model IS NULL OR model = ''"
   456|```
   457|
   458|#### ❓ Export says "directory not found"
   459|
   460|**Cause: the directory path you entered doesn't exist.** Create it first:
   461|
   462|```bash
   463|mkdir -p ~/Desktop/my-data
   464|token-stats -b hermes --export
   465|# Enter: ~/Desktop/my-data
   466|```
   467|
   468|#### ❓ `--compare` shows no data for both periods
   469|
   470|**Possible cause:** neither period has session records. Check with `--today` first.
   471|
   472|### Data scope
   473|
   474|> ⚠️ `token-stats` **only reads local agent data from this machine**.
   475|>
   476|> - If you run Hermes on PC A and Claude Code on PC B, each machine stores and reports its own data
   477|> - `token-stats` reads disk files, not cloud APIs
   478|> - To see stats on another machine, install `token-stats` there too
   479|> - All statistics are per-agent, not a cross-agent total
   480|