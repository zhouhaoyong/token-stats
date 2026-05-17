<p align="center">
  <a href="README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="README.zh.md"><strong>🇨🇳 简体中文</strong></a>
</p>

# token-stats

> 你的 AI 编码助手花了多少 tokens？一查就知道。

## 🤔 这是个啥？

你用 AI 编码助手（Claude Code、Hermes Agent、CodeX）干活的时候，每次跟大模型对话都会消耗 tokens。

**token-stats** 就是一个记账本，帮你搞清楚：

- **这次任务**花了多少 tokens？（不是总累计，只算这一回）
- **哪个模型**花得最多？
- **上下文窗口**快满了没？（满了 AI 会忘事，得换新对话）

**一个命令，4 种 Agent 通用。** 不管你是 Claude Code 用户、Hermes 用户、CodeX 用户，还是全都要，装一次就能用。

---

## ✨ 特性

| 功能 | 说明 |
|------|------|
| 🎯 **按任务统计** | `--save-baseline` 打卡 → 干活 → `--delta` 出账 |
| 🧩 **支持 4 种 Agent** | Hermes / Claude Code / OpenClaw / CodeX |
| ⚡ **实时监控** | `--watch` 开着，自动显示每一轮花了多少 |
| 🖥️ **VS Code 集成** | 装个任务，一键查看 |
| 📊 **表格展示** | 每个模型一行，上下文占用一目了然 |
| 📦 **零依赖** | 纯 Python，不需要装任何第三方库 |

---

## 🚀 安装（装一次，所有 Agent 通用）

脚本安装在 `~/.local/share/token-stats/`，全局命令在 `~/.local/bin/token-stats`。**不管你用几个 AI 工具，装这一次就够了。**

### macOS / Linux

```bash
# 1. 下载脚本到固定位置
mkdir -p ~/.local/share/token-stats
curl -o ~/.local/share/token-stats/token-stats.py \
  https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py
chmod +x ~/.local/share/token-stats/token-stats.py

# 2. 创建全局命令（ln -s 创建软链接）
mkdir -p ~/.local/bin
ln -sf ~/.local/share/token-stats/token-stats.py ~/.local/bin/token-stats

# 3. 确保 ~/.local/bin 在 PATH 中
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.zshrc
# （如果用 bash 则改为 ~/.bashrc）
source ~/.zshrc
```

### Windows PowerShell

```powershell
# 1. 下载脚本
New-Item -ItemType Directory -Force -Path "$HOME\.local\share\token-stats"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py" `
  -OutFile "$HOME\.local\share\token-stats\token-stats.py"

# 2. 创建函数（PowerShell 没有 ln -s，用函数替代）
echo "`nfunction token-stats { python3 `"$HOME\.local\share\token-stats\token-stats.py`" @args }" >> $PROFILE
. $PROFILE
```

### 验证

```bash
token-stats --version              # 显示版本号
token-stats --list-backends        # 显示支持的 Agent
token-stats --validate             # 验证数据完整性
```

---

### 可选：装 Hermes Agent 专用集成

如果你用 [Hermes Agent](https://github.com/nousresearch/hermes-agent)，可以装 skill 配置，让 Hermes 自动识别 `token-stats` 命令：

```bash
# 注意：从 ~ 目录运行
clawhub install agent-usage-stats
```

> ⚠️ `clawhub install` 会把文件装到当前目录的 `skills/` 下。
> 如果你用 Hermes，建议 `cd ~/.hermes` 再装：
> ```bash
> cd ~/.hermes && clawhub install agent-usage-stats
> ```
> 这样技能文件会进 `~/.hermes/skills/agent-usage-stats/`。

---

### 可选：VS Code 任务

把项目里的 `.vscode/tasks.json` 复制到你的项目目录，然后：

- `Cmd+Shift+P` → 输入「Tasks: Run Task」→ 选 `📊 token-stats: 实时监控`

预置了 5 个任务：
| 任务名 | 干啥的 |
|--------|--------|
| `📊 token-stats: 查看累计` | 看看已经花了多少 |
| `📊 token-stats: 开始任务` | 干活前点一下记个起点 |
| `📊 token-stats: 结束任务` | 干完活点一下看结果 |
| `📊 token-stats: 实时监控 (5s)` | 开个监控窗口，5 秒一刷 |
| `📊 token-stats: 实时监控 (10s)` | 刷得慢一点，省资源 |

---

## 📖 使用方法

### 方案 A：手动记账（最常用）

```
开干前打卡 → 正常干活 → 干完查账

token-stats --save-baseline    ← 记录起点
         ↓
用你的 AI 编码助手干活
         ↓
token-stats --delta            ← 输出账单
         ↓
📊 一张表告诉你花了多少 tokens
```

**配合 Claude Code 使用：**
```bash
# 1. 打卡
token-stats --save-baseline --backend claude-code

# 2. 启动 Claude Code 干活
claude

# 3. 退出后看账单
token-stats --delta --backend claude-code
```

**配合 Hermes Agent 使用（装 skill 后自动生效）：**
```bash
# 在 Hermes 聊天中直接打
token-stats --save-baseline    # 任务前
token-stats --delta            # 任务后
```

### 方案 B：实时监控（适合 VS Code 里边干活边盯着）

```bash
token-stats --watch
```

效果（默认每 5 秒自动检测）：
```
📡 实时监控 [claude-code] — 每 5 秒刷新 (Ctrl+C 停止)

  ⏳ 等待对话...
  [14:32] 对话 1 轮 · 消耗 4.3K tokens (deepseek-v4-flash)
        输入 3.2K / 输出 1.1K
  [14:34] 对话 1 轮 · 消耗 2.1K tokens (deepseek-v4-flash)
        输入 1.5K / 输出 0.6K

📊 本次监控汇总
  deepseek-v4-flash: 4 轮 · 15.1K tokens
  ───────────────
  总计: 4 轮 · 15.1K tokens
```

> 打开 VS Code，按 `` Ctrl+` `` 打开底部终端，运行 `token-stats --watch --backend claude-code`。
> 左边正常用 Claude Code 插件聊天，下面实时看花费。

---

## 📊 输出怎么看？

```
┌──────────────────┬──────────┬──────────────┬──────────────┬─────────┐
│      模型        │  调用次数 │   输入 tokens │  输出 tokens  │   占用  │
├──────────────────┼──────────┼──────────────┼──────────────┼─────────┤
│ deepseek-v4-pro  │    2/5   │   12,340     │   5,678      │ >100%   │
└──────────────────┴──────────┴──────────────┴──────────────┴─────────┘
 🗂  hermes · 2 次调用 · 18,018 tokens
 📦  累计: 1.4M/1,048,576 tokens (>100%)
```

| 位置 | 含义 |
|------|------|
| **左边数字**（如 `2`） | **本次任务**从打卡开始消耗的 |
| **右边数字**（如 `5`） | 这个 AI 从创建至今总共消耗 |
| **占用 %** | 上下文窗口用了多少（< 60% 正常，> 90% 该换对话） |
| 🗂 底部 | 用的哪个 Agent、总调用次数 |
| 📦 底部 | 累计上下文占用 |

---

## 🔧 更新

```bash
# 重新下载覆盖即可
curl -o ~/.local/share/token-stats/token-stats.py \
  https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py
chmod +x ~/.local/share/token-stats/token-stats.py

# 验证
token-stats --version
```

---

## 🗑️ 卸载

```bash
# 删脚本
rm -rf ~/.local/share/token-stats
rm -f ~/.local/bin/token-stats

# 如果装了 ClawHub 版本
clawhub uninstall agent-usage-stats

# 如果设了 alias，也清理一下
# macOS: 打开 ~/.zshrc 删掉 token-stats 那行
# Linux:  打开 ~/.bashrc 删掉 token-stats 那行
sed -i '' '/token-stats/d' ~/.zshrc   # macOS
# sed -i '/token-stats/d' ~/.bashrc   # Linux
source ~/.zshrc
```

---

## 🔧 环境要求

- Python 3.10+
- 不需要装任何第三方库（Python 自带的就够了）

---

## 📄 协议

MIT

---

## 🤝 贡献

欢迎 PR！特别是：
- 加新的模型上下文窗口
- 支持更多的 AI 工具
- 多语言翻译
- Bug 反馈
