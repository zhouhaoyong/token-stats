# token-stats — 选个 Agent 看它的消耗

每次运行都让你选，想看哪个 Agent 就看哪个。

## 一句话说明

你的电脑上装了多个 AI 助手（Hermes、Claude Code、CodeX、OpenClaw……），
`token-stats` 可以告诉你**每个助手到底用掉了多少 tokens**。

---

## 环境要求

装 `token-stats` 之前，你的电脑需要先有这些东西：

### 1. Python 3.8+

`token-stats` 本身是纯 Python 脚本，依赖标准库，不需要额外 pip 装任何包。

```bash
# 检查已安装
python3 --version

# 如果没装 → 去 https://www.python.org/downloads/ 下载
# macOS 通常自带 Python 3，Windows 需要手动装
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
clawhub --version   # 应该显示 v0.9.x
```

> 💡 如果你用的是 macOS 且通过 Homebrew 装过 Node.js，
> `npm install -g clawhub` 安装后会出现在 `/opt/homebrew/bin/clawhub`，
> 通常已经在你 PATH 里了，直接用就行。

---

## 安装

满足以上环境后，三行命令搞定：

```bash
# 第 1 步：从 ClawHub 安装 token-stats
clawhub install agent-usage-stats

# 第 2 步：创建全局命令（setup 命令会自动写好包装器，不需修改脚本权限）
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

好了。以后在终端直接敲 `token-stats` 就能用。

> ⚠️ 如果 `~/skills/` 目录不存在，先确认 `clawhub install` 执行时当前目录在哪里。
> ClawHub 会把技能装到 **当前目录下的 skills/ 文件夹**。
> 建议在 `~/.hermes/` 或 `~` 目录下运行安装命令。

---

## 用法

### 最简单的用法：交互式选择

```bash
token-stats
```

效果：
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

选 1 看 Hermes，选 2 看 Claude Code，**每次都要选**。

### 直接指定（跳过菜单）

如果已经知道想看哪个：

```bash
token-stats -b hermes
token-stats -b claude-code
token-stats -b codex
token-stats -b openclaw
```

### 实时监控

```bash
token-stats --watch
```

先选 Agent，然后每隔 5 秒自动刷新一次，实时看 tokens 增长。
看到差不多了按 `Ctrl+C` 停止。

也可以直接指定要监控谁：

```bash
token-stats -b hermes --watch
token-stats -b claude-code --watch 2
# 最后的数字是间隔秒数，默认 5 秒
```

### 查看本机装了哪些 Agent

```bash
token-stats --list-backends
```

✅ 表示已安装，❌ 表示没装。没装的 Agent 不会出现在菜单里。

---

## 各 Agent 的数据怎么看

| Agent | 能看到什么 |
|-------|-----------|
| **Hermes** | 当前对话的模型、上下文占用（占比 + 建议）、API 调用次数、工具调用次数、输入/输出/cache tokens、会话轮数 |
| **Claude Code** | 所有项目累计的调用次数、子代理调用次数、输入/输出/cache tokens |
| **CodeX** | 数据库里累计的总 tokens、线程数 |
| **OpenClaw** | 当前模型（含 provider）、上下文占用、输入/输出 tokens、缓存读取 |

### 数据来源位置（便于排查问题）

| Agent | 数据读哪里 |
|-------|-----------|
| Hermes | `~/.hermes/state.db` → sessions 表 |
| Claude Code | `~/.claude/projects/**/*.jsonl` |
| CodeX | `~/.codex/state_*.sqlite` → threads 表 |
| OpenClaw | `~/ai-testing-lab/openclaw/data/.../sessions.json` |

---

## 实用场景

**想知道 Hermes 用了多少上下文？**
```bash
token-stats
# 选 1 → 看到 "上下文: 123.4K/1M (11.8% ✅)"
```

**边用 Claude Code 边盯着消耗？**
```bash
token-stats -b claude-code --watch
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
# 移除 token-stats 技能
clawhub uninstall agent-usage-stats

# 删除全局命令
rm -f ~/.local/bin/token-stats

# 清理旧 alias（如果你之前设过 alias token-stats=...）
# 检查现在的 shell 配置里有么有：
grep "alias token-stats" ~/.zshrc ~/.bashrc 2>/dev/null || echo "没有发现旧的 alias"

# 如果有输出对应的行，手动删除或用 sed：
sed -i '' '/alias token-stats/d' ~/.zshrc
source ~/.zshrc
```

---

## 兼容性

| 平台 | 状态 |
|------|------|
| macOS | ✅ 完整支持 |
| Linux | ✅ 完整支持 |
| Windows | ⬜ 规划中（欢迎 PR） |

| 环境 | 要求 |
|------|------|
| Python | 3.8+（标准库，零 pip 依赖） |
| Node.js | 仅安装时需要（装 ClawHub） |

---

## 常见问题

### ❓ `python3 ~/skills/agent-usage-stats/token-stats.py setup` 提示文件不存在

ClawHub 把技能装到了执行 `clawhub install` 时所在目录的 `skills/` 文件夹下。
请确认 `~/skills/` 是否存在，或者重新在 `~` 目录下运行安装：

```bash
cd ~
clawhub install agent-usage-stats
python3 ~/skills/agent-usage-stats/token-stats.py setup
```

### ❓ `token-stats` 命令找不到

先确认 `~/.local/bin/` 在 PATH 里：

```bash
echo $PATH | grep .local/bin
# 如果没输出，先添加：
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc
source ~/.zshrc
```

### ❓ `clawhub install` 报错

检查网络和 Node.js 版本：

```bash
node --version   # 需要 v18+
npm install -g clawhub  # 重装
```

### ❓ 菜单里看不到我装的 Agent

`token-stats` 通过检查配置文件来判断 Agent 是否已安装。
这些路径存在才会显示：

- **Hermes**: `~/.hermes/state.db`
- **Claude Code**: `~/.claude/projects/`
- **CodeX**: `~/.codex/state_*.sqlite`
- **OpenClaw**: `~/ai-testing-lab/openclaw/data/.../sessions.json`

可以先跑 `token-stats --list-backends` 看具体哪个被检测到了。
