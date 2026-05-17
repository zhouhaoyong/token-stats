# token-stats — 选个 Agent 看它的消耗

每次运行都让你选，想看哪个 Agent 就看哪个。

## 一句话说明

你的电脑上装了多个 AI 助手（Hermes、Claude Code、CodeX……），
`token-stats` 可以告诉你**每个助手到底用掉了多少 tokens**。

## 安装

```bash
# 第 1 步：从 ClawHub 安装
clawhub install agent-usage-stats

# 第 2 步：创建全局命令
~/skills/agent-usage-stats/token-stats.py setup
```

好了。以后直接在终端敲 `token-stats` 就能用。

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
  [q] 退出
────────────────────────────────────────
请选择 (1-3)：
```

选 1 看 Hermes，选 2 看 Claude Code，**每次都要选**。

### 直接指定（跳过菜单）

如果已经知道想看哪个，也可以：

```bash
token-stats -b hermes
token-stats -b claude-code
token-stats -b codex
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

## 各 Agent 的数据怎么看

| Agent | 能看到什么 |
|-------|-----------|
| **Hermes** | 当前对话的模型、上下文占用、API 调用次数、工具调用、输入/输出/cache tokens |
| **Claude Code** | 所有项目累计的调用次数、子代理调用、输入/输出/cache tokens |
| **CodeX** | 数据库里累计的总 tokens、线程数 |
| **OpenClaw** | 所有会话累计的 tokens、当前模型 |

## 实用场景

**想知道 Hermes 用了多少上下文？**
```bash
token-stats
# 选 1 → 看到 "上下文: 123.4K/1M (11.8% ✅)"
```

**边用 Claude Code 边盯着消耗？**
```bash
token-stats -b claude-code --watch
# 切到 Claude Code 干活，这边实时跳动 tokans
```

**想换 Agent 了？**
```bash
token-stats
# 再选一次就行
```

## 兼容性

- ✅ macOS / Linux
- ✅ Python 3.8+
- ✅ 纯 Python 标准库，零依赖

Windows 支持请期待后续版本。

## 卸载

```bash
clawhub uninstall agent-usage-stats
rm -f ~/.local/bin/token-stats
```
