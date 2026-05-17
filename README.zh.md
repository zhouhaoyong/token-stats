<p align="center">
  <a href="README.md"><strong>🇬🇧 English</strong></a> ·
  <a href="README.zh.md"><strong>🇨🇳 简体中文</strong></a>
</p>

# token-stats

> 你的 AI 编码助手花了多少 tokens？一查就知道。


## 🤔 这是个啥？

你用 AI 编码助手（比如 Claude Code、Hermes Agent、CodeX）干活的时候，背后跟大模型说的话都是有「额度」的——每次对话都会消耗 tokens。

**token-stats** 就是一个记账本，帮你搞清楚：

- ❓ **这次任务**花了多少 tokens？（不是从开天辟地算起，是只算这一次）
- ❓ **哪个模型**花钱最多？（DeepSeek? Claude? 各花了多少？）
- ❓ **上下文窗口**快满了没？（满了 AI 会忘事，得赶紧换个新对话）

---

## ✨ 都能干点啥？

| 功能 | 说明 |
|------|------|
| 🎯 **按任务统计** | 不是总累计，只算你开始干活到干完这期间的消耗 |
| 🧩 **支持 4 种 AI 工具** | Hermes / Claude Code / OpenClaw / CodeX 都认识 |
| 📊 **表格展示** | 每个模型一行，一眼看出谁花得多 |
| ⚡ **实时监控** | 干活的时候在旁边开着，自动显示每一轮花了多少 |
| 🖥️ **VS Code 集成** | 装个任务，按快捷键就能看 |
| 🔍 **数据验证** | 数据对不对？跑一下就知道 |
| 📦 **零依赖** | 纯 Python，不需要装任何第三方库 |

---

## 🚀 怎么用？

### 第 1 步：装起来

**选你的系统：**

<details>
<summary><b>🍎 macOS</b>（点开查看）</summary>

```bash
# 方式 A：ClawHub 安装（推荐）
clawhub install agent-usage-stats

# 方式 B：直接下载（任何时候都能用）
curl -O https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py
chmod +x token-stats.py

# 然后设置命令（让系统认识 "token-stats" 这个词）
echo 'alias token-stats="python3 ~/.hermes/skills/agent-usage-stats/token-stats.py"' >> ~/.zshrc
source ~/.zshrc
```
</details>

<details>
<summary><b>🐧 Linux</b>（点开查看）</summary>

```bash
# 方式 A：ClawHub
clawhub install agent-usage-stats

# 方式 B：直接下载
curl -O https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py
chmod +x token-stats.py

# 设置命令
echo 'alias token-stats="python3 ~/.hermes/skills/agent-usage-stats/token-stats.py"' >> ~/.bashrc
source ~/.bashrc
```
</details>

<details>
<summary><b>🪟 Windows</b>（点开查看）</summary>

```powershell
# 方式 A：ClawHub
clawhub install agent-usage-stats

# 方式 B：直接下载
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py" -OutFile "token-stats.py"

# 设置命令
echo "`nfunction token-stats { python3 `"$HOME\.hermes\skills\agent-usage-stats\token-stats.py`" @args }" >> $PROFILE
. $PROFILE
```
</details>

**装好后验证一下：**
```bash
token-stats --list-backends
# 如果看到 ✅ 就说明装好了
```

#### 怎么更新到新版？

```bash
# ClawHub 安装的（更新单个 skill）
clawhub update agent-usage-stats

# ClawHub 安装的（更新所有 skill）
clawhub update

# 直接下载的（重新下载覆盖即可）
curl -O https://raw.githubusercontent.com/zhouhaoyong/token-stats/main/token-stats.py
chmod +x token-stats.py
```

---

### 第 2 步：开始记账

#### 方案 A：手动模式（最常用，推荐新手）

```
┌─────────────────────────────────────────┐
│  开干前打个卡 → 正常干活 → 干完查账     │
│                                         │
│  token-stats --save-baseline            │
│         ↓                               │
│  用你的 AI 编码助手干活                  │
│         ↓                               │
│  token-stats --delta                    │
│         ↓                               │
│  📊 一张表告诉你花了多少 tokens          │
└─────────────────────────────────────────┘
```

**举个例子：**
```bash
# 1️⃣ 记录起点（干活前）
$ token-stats --save-baseline
✅ [hermes] 基线已保存

# 2️⃣ 正常用你的 AI 助手干活...

# 3️⃣ 看看花了多少（干完活）
$ token-stats --delta
┌──────────────────┬──────────┬──────────────┬──────────────┬─────────┐
│      模型        │  调用次数 │   输入 tokens │  输出 tokens  │   占用  │
├──────────────────┼──────────┼──────────────┼──────────────┼─────────┤
│ deepseek-v4-pro  │    2/5   │   12,340     │   5,678      │ >100%   │
└──────────────────┴──────────┴──────────────┴──────────────┴─────────┘
 🗂  hermes · 2 次调用 · 18,018 tokens
 📦  累计: 1.4M/1,048,576 tokens (>100%)
```

#### 方案 B：实时监控模式（适合 VS Code 里边干活边盯着）

```bash
# 开一个监控窗口，让它自动刷新
token-stats --watch
```

效果（每 10 秒自动刷新）：
```
📡 实时监控 [hermes] — 每 10 秒刷新一次 (Ctrl+C 停止)

  等待数据变化...
[14:32:10] deepseek-v4-flash +4.3K tokens (1 次)
[14:34:55] deepseek-v4-flash +2.1K tokens (1 次)
[14:37:12] deepseek-v4-flash +8.7K tokens (2 次)

━━━ 本次监控会话合计 ━━━
  deepseek-v4-flash: 4 次调用 · 15.1K tokens
  ───────────────
  合计: 4 次调用 · 15.1K tokens
```

> **小提示：** `--watch 5` 可以改成每 5 秒刷一次，刷得更快。

---

### 第 3 步：配 VS Code 一起用

如果你在用 VS Code 里的 Claude Code 插件，可以这样配合：

#### 方法一：终端分栏模式（推荐）

```
VS Code 窗口
┌──────────────────────────────────────┐
│                                      │
│  [代码编辑区]                         │
│                                      │
├──────────────────────────────────────┤
│  底部终端（Ctrl+\` 打开）             │
│                                      │
│  $ token-stats --watch --backend     │
│    claude-code                       │
│                                      │
│  [14:32] +1.2K tokens (1 次调用)     │
│  [14:35] +3.4K tokens (2 次调用)     │
│                                      │
└──────────────────────────────────────┘
```

打开 VS Code，按 `` Ctrl+` `` 打开终端，输入：
```bash
token-stats --watch --backend claude-code
```

然后左边正常用 Claude Code 插件聊天，下面实时看花费。按 `Ctrl+C` 停止。

#### 方法二：VS Code 任务（快捷键）

把项目里的 `.vscode/tasks.json` 复制到你的项目目录，然后：

- `Cmd+Shift+P` → 输入「Tasks: Run Task」→ 选 `📊 token-stats: 实时监控`
- 或者设个快捷键，一键启动

配置里已经预置了 5 个任务：
| 任务名 | 干啥的 |
|--------|--------|
| `📊 token-stats: 查看累计` | 看看已经花了多少 |
| `📊 token-stats: 开始任务` | 干活前点一下记个起点 |
| `📊 token-stats: 结束任务` | 干完活点一下看结果 |
| `📊 token-stats: 实时监控 (10s)` | 开个监控窗口，10秒一刷 |
| `📊 token-stats: 实时监控 (5s)` | 刷得更快（5秒） |

---

### 其他常用命令

```bash
# 查看当前总共花了多少
token-stats --summary

# 看看有哪几个 AI 工具可以用
token-stats --list-backends

# 验证数据对不对
token-stats --validate

# 如果用的不是 Hermes，指定一下工具
token-stats --save-baseline --backend claude-code   # 用 Claude Code 的话
token-stats --delta         --backend claude-code
```

---

## 📊 输出怎么看？

```
┌──────────────────┬──────────┬──────────────┬──────────────┬─────────┐
│      模型        │  调用次数 │   输入 tokens │  输出 tokens  │   占用  │
├──────────────────┼──────────┼──────────────┼──────────────┼─────────┤
│ deepseek-v4-pro  │    2/5   │   12,340     │   5,678      │ >100%   │
│ claude-sonnet-4  │    1/5   │   8,234      │   3,456      │ 14.5%✅ │
│ ⬇subagent        │    3/12  │   2,100      │   1,200      │ 58.4%✅ │
└──────────────────┴──────────┴──────────────┴──────────────┴─────────┘
 🗂  claude-code · 3/1720 次调用 · 34,009 tokens · 子代理: 3/12
 📦  累计: 2,355K/1,048,576 tokens (>100%)
```

**每个数字啥意思：**
| 位置 | 含义 |
|------|------|
| **左边数字**（如 `2`） | **这次任务**从打卡开始到现在的消耗 |
| **右边数字**（如 `5`） | 这个 AI 从创建到现在总共花了多少 |
| **占用 %** | 上下文窗口用了多少（< 60% 正常，> 90% 该换对话了） |
| 🗂 底部 | 用的哪个 AI 工具、总共的任务统计 |
| 📦 底部 | 累计上下文占用（超过 100% 说明跨了多个会话） |

---

## 🤔 举个完整例子

**场景：** 你用 Claude Code 写一个 API 接口，想知道这次花了多少 tokens

```bash
# 终端 1：记录起点
$ token-stats --save-baseline --backend claude-code
✅ [claude-code] 基线已保存

# 然后打开 Claude Code 开始干活...
# 跟 AI 聊了 10 轮，写了代码，调试通过

# 干完活，查看花费
$ token-stats --delta --backend claude-code
┌──────────────────┬──────────┬──────────────┬──────────────┬─────────┐
│ deepseek-v4-pro  │   10/15  │   45,200     │   12,300     │  4.1%✅ │
└──────────────────┴──────────┴──────────────┴──────────────┴─────────┘
 🗂  claude-code · 10 次调用 · 57,500 tokens
 📦  累计: 57,500/1,048,576 tokens (5.5%✅)
```

> 10 次对话花了 57,500 tokens，相当于上下文 1M 的 5.5%，还很富裕 👍

---

## 🔧 需要啥环境？

- Python 3.10 以上
- 不需要装任何第三方库（Python 自带的就够了）
- 装了上面 4 种 AI 工具中的至少一种

---

## 📄 开源协议

MIT — 随便用，随便改

---

## 🤝 想帮忙？

欢迎提 PR！特别是：
- 加新的模型上下文窗口数字
- 支持更多的 AI 工具
- 多语言翻译
- 发现 bug 告诉我
