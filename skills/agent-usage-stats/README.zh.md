     1|# token-stats — 选个 Agent 看它的消耗
     2|
     3|每次运行都让你选，想看哪个 Agent 就看哪个。
     4|
     5|## 一句话说明
     6|
     7|你的电脑上装了多个 AI 助手（Hermes、Claude Code、CodeX、OpenClaw……），
     8|`token-stats` 可以告诉你**每个助手到底用掉了多少 tokens**。
     9|
    10|> ⚠️ **重要说明：本工具仅统计本机的 Agent 数据。**
    11|> 如果你在不同 PC 或服务器上运行 Agent，各自的数据仅保存在各台机器上，
    12|> 无法跨机器统计。每台机器需要各自安装本工具查看。
    13|> 
    14|> 所有统计都是基于你选择的某个 Agent 来查询的，不是特指某一个。
    15|
    16|---
    17|
    18|## 环境要求
    19|
    20|装 `token-stats` 之前，你的电脑需要先有这些东西：
    21|
    22|### 1. Python 3.8+
    23|
    24|`token-stats` 本身是纯 Python 脚本，依赖标准库，不需要额外 pip 装任何包。
    25|
    26|```bash
    27|# 检查已安装
    28|python3 --version
    29|
    30|# 如果没装 → 去 https://www.python.org/downloads/ 下载
    31|# macOS 通常自带 Python 3，Windows 需要手动装
    32|```
    33|
    34|### 2. Node.js（安装工具时需要）
    35|
    36|`token-stats` 通过 **ClawHub CLI** 安装。ClawHub 是个 Node.js 命令行工具。
    37|
    38|```bash
    39|# 检查已安装
    40|node --version
    41|
    42|# 如果没装 → 去 https://nodejs.org 下载（选 LTS 版本）
    43|```
    44|
    45|装好 Node.js 后会自动带上 `npm`，用来装 ClawHub。
    46|
    47|### 3. ClawHub CLI
    48|
    49|```bash
    50|# 安装（npm 全局安装）
    51|npm install -g clawhub
    52|
    53|# 验证
    54|clawhub --version   # 应该显示 v0.9.x
    55|```
    56|
    57|> 💡 如果你用的是 macOS 且通过 Homebrew 装过 Node.js，
    58|> `npm install -g clawhub` 安装后会出现在 `/opt/homebrew/bin/clawhub`，
    59|> 通常已经在你 PATH 里了，直接用就行。
    60|
    61|---
    62|
    63|## 安装
    64|
    65|满足以上环境后，三行命令搞定：
    66|
    67|```bash
    68|# 第 1 步：从 ClawHub 安装 token-stats
    69|clawhub install agent-usage-stats
    70|
    71|# 第 2 步：创建全局命令（setup 命令会自动写好包装器，不需修改脚本权限）
    72|python3 ~/skills/agent-usage-stats/token-stats.py setup
    73|```
    74|
    75|好了。以后在终端直接敲 `token-stats` 就能用。
    76|
    77|### 验证安装成功
    78|
    79|```bash
    80|# 验证 1：版本号
    81|token-stats --version
    82|# 输出: token-stats v2.0.7
    83|
    84|# 验证 2：看本机已安装的 Agent
    85|token-stats --list-backends
    86|# 输出示例:
    87|#   ✅ Hermes
    88|#   ✅ Claude Code
    89|#   ❌ CodeX
    90|#   ❌ OpenClaw
    91|
    92|# 验证 3：直接看某个 Agent 的统计
    93|token-stats -b hermes
    94|# 输出示例:
    95|# 📊 Hermes
    96|#   deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 调用 13 次
    97|```
    98|
    99|如果以上三条都正常输出，说明安装完全成功 🎉
   100|
   101|> ⚠️ 如果 `~/skills/` 目录不存在，先确认 `clawhub install` 执行时当前目录在哪里。
   102|> ClawHub 会把技能装到 **当前目录下的 skills/ 文件夹**。
   103|> 建议在 `~/.hermes/` 或 `~` 目录下运行安装命令。
   104|
   105|---
   106|
   107|## 用法
   108|
   109|### 快速查看
   110|
   111|```bash
   112|# 交互式选择
   113|token-stats
   114|
   115|# 直接指定 Agent（跳过菜单）
   116|token-stats -b hermes
   117|token-stats -b claude-code
   118|token-stats -b codex
   119|token-stats -b openclaw
   120|
   121|# 查看本机所有 Agent
   122|token-stats --all
   123|
   124|# 当前快照（同默认）
   125|token-stats -b hermes --now
   126|
   127|# 详细模式（显示更多信息）
   128|token-stats -b hermes --detail
   129|```
   130|
   131|所有命令都支持切换 Agent 名称，例如：
   132|- `-b hermes` → Hermes
   133|- `-b claude-code` → Claude Code
   134|- `-b codex` → CodeX
   135|- `-b openclaw` → OpenClaw
   136|
   137|输出示例（每个模型一行，仅显示有数据的模型）：
   138|```
   139|📊 Hermes
   140|  deepseek-v4-flash | 上下文 62.4K/1.05M (6.0% ✅) | 输入 57.1K | 输出 5.4K | 缓存 480.6K | 调用 13 次 | 第 16 轮 "..."
   141|
   142|📊 Claude Code
   143|  deepseek-v4-pro | 上下文 2.60M/1.05M (>100%) | 输入 1.78M | 输出 823.0K | 缓存 341.48M | 调用 1723 次
   144|  Qwen3-Coder-30B | 上下文 23.0K/131.1K (17.6% ✅) | 输入 22.9K | 输出 131 | 调用 1 次
   145|```
   146|
   147|### 时间段查询
   148|
   149|查看某段时间内的总消耗（不显示上下文占比，显示会话数）：
   150|
   151|```bash
   152|# 今天（各 Agent 通用）
   153|token-stats -b hermes --today
   154|token-stats -b claude-code --today
   155|token-stats -b codex --today
   156|token-stats -b openclaw --today
   157|
   158|# 昨天
   159|token-stats -b hermes --yesterday
   160|
   161|# 本周（周一到现在）
   162|token-stats -b hermes --week
   163|
   164|# 最近 7 天
   165|token-stats -b hermes --last-7d
   166|
   167|# 自定义日期范围（从当天 00:00:00 到当天 23:59:59）
   168|token-stats -b hermes --from 2026-01-01 --to 2026-05-18
   169|token-stats -b claude-code --from 2026-01-01 --to 2026-05-18
   170|```
   171|
   172|时间段输出示例（无上下文占比，显示会话数）：
   173|```
   174|📊 Hermes
   175|  deepseek-v4-flash | 总计 988.9K | 输入 660.5K | 输出 327.0K | 缓存 72.66M | 调用 699 次 | 4 轮会话
   176|```
   177|
   178|### 对比两个时间段
   179|
   180|```bash
   181|# 快捷标签对比
   182|token-stats -b hermes --compare --a today --b yesterday
   183|token-stats -b hermes --compare --a this-week --b last-week
   184|
   185|# 单天对比
   186|token-stats -b hermes --compare --a 2026-01-01 --b 2026-05-18
   187|token-stats -b claude-code --compare --a 2026-01-01 --b 2026-05-18
   188|
   189|# 时间段对比（YYYY-MM-DD~YYYY-MM-DD）
   190|token-stats -b hermes --compare --a 2026-01-01~2026-01-07 --b 2026-01-08~2026-05-18
   191|```
   192|
   193|对比输出示例：
   194|```
   195|📊 对比: "today" vs "yesterday"  [Hermes]
   196|══════════════════════════════════════════════════════════════════════
   197|  模型                           |            A |            B |           变化
   198|──────────────────────────────────────────────────────────────────────
   199|  deepseek-v4-flash            |       988.9K |        65.4K |      -923.5K
   200|──────────────────────────────────────────────────────────────────────
   201|  总计                           |       988.9K |        65.4K |      -923.5K
   202|```
   203|
   204|### 导出数据
   205|
   206|交互式选择目录和格式：
   207|
   208|```bash
   209|# 导出当前最新会话
   210|token-stats -b hermes --export
   211|token-stats -b claude-code --export
   212|token-stats -b codex --export
   213|
   214|# 导出今天的数据
   215|token-stats -b hermes --today --export
   216|
   217|# 导出昨天的数据
   218|token-stats -b hermes --yesterday --export
   219|
   220|# 导出过去 7 天
   221|token-stats -b hermes --last-7d --export
   222|
   223|# 导出指定时间段
   224|token-stats -b hermes --from 2026-01-01 --to 2026-05-18 --export
   225|token-stats -b claude-code --from 2026-01-01 --to 2026-05-18 --export
   226|```
   227|
   228|流程：先显示统计 → 请输入导出目录路径 → 选择 JSON 还是 CSV。
   229|
   230|支持三大操作系统路径：
   231|- macOS/Linux: `~/Desktop`, `/tmp/data`
   232|- Windows: `C:\Users\xxx\Documents`
   233|
   234|### 实时监控
   235|
   236|```bash
   237|# 交互式选择 → 监控
   238|token-stats --watch
   239|
   240|# 直接指定
   241|token-stats -b hermes --watch
   242|token-stats -b claude-code --watch 2   # 2 秒刷新一次
   243|```
   244|
   245|每 5 秒自动刷新（可自定义间隔），Ctrl+C 停止后输出汇总表。
   246|
   247|### 查看本机装了哪些 Agent
   248|
   249|```bash
   250|token-stats --list-backends
   251|```
   252|
   253|✅ 表示已安装，❌ 表示没装。没装的 Agent 不会出现在菜单里。
   254|
   255|---
   256|
   257|## 命令大全
   258|
   259|所有命令都支持将 `-b hermes` 中的 `hermes` 替换为：`claude-code`、`codex`、`openclaw`。
   260|
   261|### 基础
   262|
   263|| 命令 | 说明 |
   264||------|------|
   265|| `token-stats` | 交互式菜单选择 Agent → 查看统计 |
   266|| `token-stats -b <name>` | 直接指定 Agent，跳过菜单 |
   267|| `token-stats --version` | 显示版本号 |
   268|| `token-stats -b <name> --detail` | 详细模式（同默认） |
   269|| `token-stats -b <name> --now` | 当前快照（同默认） |
   270|
   271|### 快速时间段
   272|
   273|| 命令 | 说明 |
   274||------|------|
   275|| `token-stats -b <name> --today` | 今日统计（当天 00:00:00 ~ 现在） |
   276|| `token-stats -b <name> --yesterday` | 昨日统计（昨天全天） |
   277|| `token-stats -b <name> --week` | 本周统计（周一开始至今） |
   278|| `token-stats -b <name> --last-7d` | 最近 7 天 |
   279|| `token-stats -b <name> --from 2026-01-01 --to 2026-05-18` | 自定义时间段（起始日 00:00 到结束日 23:59） |
   280|
   281|### 对比
   282|
   283|| 命令 | 说明 |
   284||------|------|
   285|| `token-stats -b <name> --compare --a today --b yesterday` | 快捷标签对比 |
   286|| `token-stats -b <name> --compare --a this-week --b last-week` | 本周 vs 上周 |
   287|| `token-stats -b <name> --compare --a 2026-01-01 --b 2026-05-18` | 两个单天对比 |
   288|| `token-stats -b <name> --compare --a 2026-01-01~2026-01-07 --b 2026-01-08~2026-05-18` | 自定义时间段对比 |
   289|
   290|**`--a` / `--b` 支持的格式：**
   291|- `today` — 今天
   292|- `yesterday` — 昨天
   293|- `this-week` — 本周（周一起）
   294|- `last-week` — 上周
   295|- `2026-01-01` — 单天
   296|- `2026-01-01~2026-01-07` — 时间段（起始~结束）
   297|
   298|### 导出
   299|
   300|| 命令 | 说明 |
   301||------|------|
   302|| `token-stats -b <name> --export` | 导出当前统计（交互式选目录和格式） |
   303|| `token-stats -b <name> --today --export` | 导出今日统计 |
   304|| `token-stats -b <name> --yesterday --export` | 导出昨日统计 |
   305|| `token-stats -b <name> --last-7d --export` | 导出近 7 天统计 |
   306|| `token-stats -b <name> --from 2026-01-01 --to 2026-05-18 --export` | 导出指定时间段统计 |
   307|
   308|### 实时监控
   309|
   310|| 命令 | 说明 |
   311||------|------|
   312|| `token-stats --watch` | 交互式选 Agent → 每 5 秒刷新（Ctrl+C 停止） |
   313|| `token-stats -b <name> --watch` | 直接指定 Agent，默认 5 秒 |
   314|| `token-stats -b <name> --watch 10` | 自定义间隔 10 秒 |
   315|
   316|### 多 Agent
   317|
   318|| 命令 | 说明 |
   319||------|------|
   320|| `token-stats --all` | 查看本机所有 Agent 统计 |
   321|| `token-stats --list-backends` | 列出已安装的 Agent |
   322|
   323|### 安装与维护
   324|
   325|| 命令 | 说明 |
   326||------|------|
   327|| `clawhub install agent-usage-stats` | 从 ClawHub 安装 |
   328|| `token-stats --setup` | 创建 `~/.local/bin/token-stats` 全局命令 |
   329|
   330|> 💡 以上所有命令也可以通过 `token-stats --help` 在线查看。
   331|
   332|---
   333|
   334|## 各 Agent 的数据怎么看
   335|
   336|每次运行输出都以 `📊 Agent名称` 开头，下面每行是一个**有数据的模型**（未使用的不显示）。
   337|
   338|| Agent | 能看到什么 |
   339||-------|-----------|
   340|| **Hermes** | 当前会话的模型、上下文占用（占比 + 提示）、输入/输出/cache tokens、API 调用次数、会话轮数 |
   341|| **Claude Code** | 各模型的上下文占用、调用次数、子代理次数、会话/项目总数 |
   342|| **CodeX** | 各模型的线程数（tokens 在 CodeX 中可能为 0，此时仅显示会话数） |
   343|| **OpenClaw** | 当前模型（含 provider）、上下文占用、输入/输出 tokens、Agent 数量 |
   344|
   345|### 数据来源位置（便于排查问题）
   346|
   347|| Agent | 数据读哪里 |
   348||-------|-----------|
   349|| Hermes | `~/.hermes/state.db` → sessions 表 |
   350|| Claude Code | `~/.claude/projects/**/*.jsonl` |
   351|| CodeX | `~/.codex/state_*.sqlite` → threads 表 |
   352|| OpenClaw | `~/ai-testing-lab/openclaw/data/.../sessions.json` |
   353|
   354|---
   355|
   356|## 实用场景
   357|
   358|**想知道 Hermes 用了多少上下文？**
   359|```bash
   360|token-stats
   361|# 选 1 → 看到 "上下文: 123.4K/1M (11.8% ✅)"
   362|```
   363|
   364|**边用 Claude Code 边盯着消耗？**
   365|```bash
   366|token-stats -b claude-code --watch
   367|# 切到 Claude Code 干活，这边实时跳动 tokens
   368|```
   369|
   370|**想换 Agent 了？**
   371|```bash
   372|token-stats
   373|# 再选一次就行
   374|```
   375|
   376|---
   377|
   378|## 卸载
   379|
   380|```bash
   381|# 移除 token-stats 技能
   382|clawhub uninstall agent-usage-stats
   383|
   384|# 删除全局命令
   385|rm -f ~/.local/bin/token-stats
   386|
   387|# 清理旧 alias（如果你之前设过 alias token-stats=...）
   388|# 检查现在的 shell 配置里有么有：
   389|grep "alias token-stats" ~/.zshrc ~/.bashrc 2>/dev/null || echo "没有发现旧的 alias"
   390|
   391|# 如果有输出对应的行，手动删除或用 sed：
   392|sed -i '' '/alias token-stats/d' ~/.zshrc
   393|source ~/.zshrc
   394|```
   395|
   396|---
   397|
   398|## 兼容性
   399|
   400|| 平台 | 状态 |
   401||------|------|
   402|| macOS | ✅ 完整支持 |
   403|| Linux | ✅ 完整支持 |
   404|| Windows | ⬜ 规划中（欢迎 PR） |
   405|
   406|| 环境 | 要求 |
   407||------|------|
   408|| Python | 3.8+（标准库，零 pip 依赖） |
   409|| Node.js | 仅安装时需要（装 ClawHub） |
   410|
   411|---
   412|
   413|## 常见问题与排查指南
   414|
   415|### 安装问题
   416|
   417|#### ❓ `clawhub install agent-usage-stats` 报错
   418|
   419|**可能原因：网络问题或 Node.js 版本过旧。**
   420|
   421|```bash
   422|# 检查 Node.js 版本（需要 v18+）
   423|node --version
   424|
   425|# 重装 ClawHub
   426|npm install -g clawhub
   427|
   428|# 如果在国内网络慢，可尝试
   429|npm install -g clawhub --registry=https://registry.npmmirror.com
   430|```
   431|
   432|#### ❓ `python3 ~/skills/agent-usage-stats/token-stats.py setup` 提示文件不存在
   433|
   434|**原因：ClawHub 把技能装到了执行 `clawhub install` 时所在目录的 `skills/` 文件夹下。**
   435|
   436|```bash
   437|# 先看 skills 装在哪里了
   438|find ~ -name "token-stats.py" -type f 2>/dev/null
   439|
   440|# 找到后 cd 到对应目录执行 setup
   441|cd ~
   442|clawhub install agent-usage-stats
   443|python3 ~/skills/agent-usage-stats/token-stats.py setup
   444|```
   445|
   446|#### ❓ `token-stats` 命令找不到
   447|
   448|**原因：`~/.local/bin/` 不在 PATH 中。**
   449|
   450|```bash
   451|# 先确认是否在 PATH 里
   452|echo $PATH | grep .local/bin
   453|
   454|# 如果没输出，先添加：
   455|echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc
   456|source ~/.zshrc
   457|
   458|# 或者直接用完整路径运行
   459|~/.local/bin/token-stats --version
   460|```
   461|
   462|#### ❓ 执行 `token-stats` 报 `Permission denied`
   463|
   464|**原因：包装器脚本没有执行权限。**
   465|
   466|```bash
   467|chmod +x ~/.local/bin/token-stats
   468|# 或者重新执行 setup
   469|python3 ~/skills/agent-usage-stats/token-stats.py setup
   470|```
   471|
   472|### 运行问题
   473|
   474|#### ❓ 菜单里看不到我装的 Agent
   475|
   476|**原因：`token-stats` 通过检查特定路径来判断 Agent 是否已安装。** 这些路径存在才会显示：
   477|
   478|| Agent | 检测路径 |
   479||-------|---------|
   480|| **Hermes** | `~/.hermes/state.db` |
   481|| **Claude Code** | `~/.claude/projects/` |
   482|| **CodeX** | `~/.codex/state_*.sqlite` |
   483|| **OpenClaw** | `~/ai-testing-lab/openclaw/data/agents/main/sessions/sessions.json` |
   484|
   485|可以先用 `token-stats --list-backends` 看具体哪个被检测到了。
   486|
   487|#### ❓ 统计显示「无数据」或数字为 0
   488|
   489|**可能原因：**
   490|
   491|1. **Agent 虽然装了但还没使用过** → 先去用一下再回来查
   492|2. **数据文件路径不对** → 运行 `token-stats --list-backends` 确认是否被检测到
   493|3. **时间段内没有数据** → 如果是 `--today` 或 `--from 2026-01-01`，确认该时间段内确实有会话
   494|
   495|#### ❓ 对比结果显示 `unknown` 模型
   496|
   497|**Hermes 数据库中部分会话的 model 字段为空**，不影响正常统计。可以用这个命令排查：
   498|
   499|```bash
   500|sqlite3 ~/.hermes/state.db "SELECT DISTINCT model FROM sessions WHERE model IS NULL OR model = ''"
   501|