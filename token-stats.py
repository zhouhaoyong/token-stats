#!/usr/bin/env python3
"""
token-stats — 选个 Agent 看它的消耗

用法:
  token-stats             交互式菜单：选 Agent → 看统计
  token-stats --watch     交互式菜单：选 Agent → 实时监控
  token-stats -b hermes   跳过菜单，直接查 Hermes
  token-stats -b claude-code --watch   跳过菜单，监控 Claude Code

安装:
  clawhub install agent-usage-stats
  token-stats setup        创建 ~/.local/bin/token-stats 软链
"""

import argparse
import json
import os
import re
import signal
import sqlite3
import sys
import time
import glob
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

VERSION = "2.0.0"


# ═══════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════

def fmt_num(n: int) -> str:
    if n < 1000:
        return str(n)
    elif n < 1_000_000:
        return f"{n/1000:.1f}K"
    else:
        return f"{n/1_000_000:.2f}M"


def fmt_pct(pct: float) -> str:
    if pct >= 100:
        return ">100%"
    elif pct >= 90:
        return f"{pct:.1f}% 🚨"
    elif pct >= 60:
        return f"{pct:.1f}% ⚠️"
    else:
        return f"{pct:.1f}% ✅"


MODEL_CONTEXT_MAP = {
    "deepseek-v4-flash": 1_048_576,
    "deepseek-v4": 1_048_576,
    "deepseek-chat": 1_048_576,
    "deepseek-reasoner": 1_048_576,
    "deepseek-v3": 131_072,
    "gpt-4o": 131_072,
    "gpt-4o-mini": 131_072,
    "claude-sonnet-4": 204_800,
    "claude-opus-4": 204_800,
    "claude-haiku-3.5": 204_800,
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.0-flash": 1_048_576,
    "qwen3": 131_072,
    "qwen-plus": 131_072,
    "llama-3.1": 131_072,
    "mistral-large": 131_072,
}

DEFAULT_CONTEXT = 131_072


def detect_context(model_name: str) -> int:
    if not model_name:
        return DEFAULT_CONTEXT
    m = model_name.lower().strip()
    if m in MODEL_CONTEXT_MAP:
        return MODEL_CONTEXT_MAP[m]
    for key, val in sorted(MODEL_CONTEXT_MAP.items(), key=lambda x: -len(x[0])):
        if m.startswith(key):
            return val
    return DEFAULT_CONTEXT


# ═══════════════════════════════════════════════════
#  Agent 检测 & 统计接口
# ═══════════════════════════════════════════════════

@dataclass
class AgentData:
    """单个 Agent 的统计数据"""
    name: str
    display_name: str
    stats: dict  # 关键字段描述
    raw: str     # 可读的统计摘要


class BaseAgent(ABC):
    """Agent 检测器基类"""

    @staticmethod
    @abstractmethod
    def name() -> str: ...

    @staticmethod
    @abstractmethod
    def display_name() -> str: ...

    @staticmethod
    @abstractmethod
    def detect() -> bool: ...

    @abstractmethod
    def collect(self) -> AgentData: ...

    def watch(self, interval: int = 5) -> None:
        """实时监控模式"""
        running = True

        def _on_signal(sig, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)

        print(f"\n📡 实时监控 [{self.display_name()}] — 每 {interval} 秒刷新 (Ctrl+C 停止)\n")

        # 首次基线
        data_first = self.collect()
        bl_input = data_first.stats.get("input_tokens", 0)
        bl_output = data_first.stats.get("output_tokens", 0)
        bl_calls = data_first.stats.get("api_calls", 0)

        print(f"初始: {fmt_num(bl_input + bl_output)} tokens, {bl_calls} 次调用\n")

        while running:
            time.sleep(interval)
            if not running:
                break
            try:
                data = self.collect()
            except Exception as e:
                print(f"  ⚠️ {e}")
                continue

            now_input = data.stats.get("input_tokens", 0)
            now_output = data.stats.get("output_tokens", 0)
            now_calls = data.stats.get("api_calls", 0)

            delta_tok = (now_input + now_output) - (bl_input + bl_output)
            delta_calls = now_calls - bl_calls

            if delta_tok > 0 or delta_calls > 0:
                ts = datetime.now().strftime("%H:%M:%S")
                model = data.stats.get("model", "?")
                print(f"  [{ts}] +{fmt_num(delta_tok)} tokens ({delta_calls} 次调用) · 模型: {model}")
                bl_input, bl_output, bl_calls = now_input, now_output, now_calls
            elif delta_tok < 0 or delta_calls < 0:
                # 会话切换，重置基线
                bl_input, bl_output, bl_calls = now_input, now_output, now_calls

        print("\n👋 监控已停止")


# ═══════════════════════════════════════════════════
#  Hermes
# ═══════════════════════════════════════════════════

HERMES_DB = os.path.expanduser("~/.hermes/state.db")


class HermesAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "hermes"

    @staticmethod
    def display_name() -> str:
        return "Hermes"

    @staticmethod
    def detect() -> bool:
        return os.path.exists(HERMES_DB)

    def collect(self) -> AgentData:
        conn = sqlite3.connect(HERMES_DB)
        conn.row_factory = sqlite3.Row

        # 最新会话
        cur = conn.execute(
            "SELECT id, model, input_tokens, output_tokens, cache_read_tokens, "
            "api_call_count, tool_call_count, title "
            "FROM sessions ORDER BY started_at DESC LIMIT 1"
        )
        row = cur.fetchone()

        if not row:
            conn.close()
            return AgentData(
                name="hermes", display_name="Hermes",
                stats={}, raw="Hermes: 尚无会话记录"
            )

        model = row["model"] or "unknown"
        inp = row["input_tokens"] or 0
        out = row["output_tokens"] or 0
        cache = row["cache_read_tokens"] or 0
        calls = row["api_call_count"] or 0
        tools = row["tool_call_count"] or 0
        title = row["title"] or "无标题"

        # 所有会话累计
        cur2 = conn.execute("SELECT COUNT(*) as cnt FROM sessions")
        session_count = cur2.fetchone()["cnt"]
        conn.close()

        cw = detect_context(model)
        total = inp + out
        pct = round(total / cw * 100, 1) if cw else 0

        stats = {
            "model": model,
            "input_tokens": inp,
            "output_tokens": out,
            "cache_read": cache,
            "api_calls": calls,
            "tool_calls": tools,
            "context_window": cw,
            "context_pct": pct,
            "total_tokens": total,
            "session_count": session_count,
            "title": title,
        }

        raw = (
            f"📊 Hermes — {model}\n"
            f"  上下文: {fmt_num(total)}/{fmt_num(cw)} ({fmt_pct(pct)})\n"
            f"  API 调用: {calls} 次 | 工具调用: {tools} 次\n"
            f"  输入: {fmt_num(inp)} | 输出: {fmt_num(out)} | 缓存读取: {fmt_num(cache)}\n"
            f"  会话: 第 {session_count} 轮 \"{title}\""
        )

        return AgentData(name="hermes", display_name="Hermes", stats=stats, raw=raw)


# ═══════════════════════════════════════════════════
#  Claude Code
# ═══════════════════════════════════════════════════

CLAUDE_DIR = os.path.expanduser("~/.claude")


class ClaudeCodeAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "claude-code"

    @staticmethod
    def display_name() -> str:
        return "Claude Code"

    @staticmethod
    def detect() -> bool:
        return os.path.isdir(os.path.join(CLAUDE_DIR, "projects"))

    def _find_sessions(self):
        projects_dir = os.path.join(CLAUDE_DIR, "projects")
        if not os.path.isdir(projects_dir):
            return []
        sessions = []
        for proj in os.listdir(projects_dir):
            proj_dir = os.path.join(projects_dir, proj)
            if not os.path.isdir(proj_dir):
                continue
            for fname in os.listdir(proj_dir):
                if fname.endswith(".jsonl") and not fname.endswith(".trajectory.jsonl"):
                    fpath = os.path.join(proj_dir, fname)
                    sessions.append((proj, fname, fpath))
        return sorted(sessions, key=lambda x: os.path.getmtime(x[2]), reverse=True)

    def collect(self) -> AgentData:
        sessions = self._find_sessions()
        if not sessions:
            return AgentData(
                name="claude-code", display_name="Claude Code",
                stats={}, raw="Claude Code: 尚无会话记录"
            )

        total_calls = 0
        total_input = 0
        total_output = 0
        total_cache = 0
        total_sub = 0
        models = set()
        project_names = set()

        # 读取最近 10 个会话的所有消息
        for proj, fname, fpath in sessions[:10]:
            project_names.add(proj)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if msg.get("type") == "assistant":
                            model = msg.get("message", {}).get("model") or msg.get("model", "unknown")
                            if not model.startswith("<"):
                                models.add(model)
                            usage = msg.get("message", {}).get("usage") or msg.get("usage", {})
                            total_calls += 1
                            total_input += usage.get("input_tokens", 0)
                            total_output += usage.get("output_tokens", 0)
                            total_cache += usage.get("cache_read_input_tokens", 0)
                        tool_result = msg.get("toolUseResult")
                        if tool_result and "usage" in tool_result:
                            total_sub += 1
            except Exception:
                continue

        stats = {
            "model": ", ".join(sorted(models)) if models else "unknown",
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_read": total_cache,
            "api_calls": total_calls,
            "sub_calls": total_sub,
            "total_tokens": total_input + total_output,
            "session_count": len(sessions),
            "projects": len(project_names),
        }

        raw = (
            f"📊 Claude Code\n"
            f"  模型: {', '.join(sorted(models)) if models else 'unknown'}\n"
            f"  总调用: {total_calls} 次 | 子代理: {total_sub} 次\n"
            f"  输入: {fmt_num(total_input)} | 输出: {fmt_num(total_output)}\n"
            f"  缓存读取: {fmt_num(total_cache)}\n"
            f"  会话文件: {len(sessions)} 个 | 项目: {len(project_names)} 个"
        )

        return AgentData(name="claude-code", display_name="Claude Code", stats=stats, raw=raw)


# ═══════════════════════════════════════════════════
#  CodeX
# ═══════════════════════════════════════════════════

def _find_codex_db() -> Optional[str]:
    codex_dir = os.path.expanduser("~/.codex")
    if not os.path.isdir(codex_dir):
        return None
    dbs = sorted(
        [f for f in os.listdir(codex_dir) if re.match(r'^state_\d+\.sqlite$', f)],
        reverse=True
    )
    return os.path.join(codex_dir, dbs[0]) if dbs else None


class CodeXAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "codex"

    @staticmethod
    def display_name() -> str:
        return "CodeX"

    @staticmethod
    def detect() -> bool:
        return _find_codex_db() is not None

    def collect(self) -> AgentData:
        db = _find_codex_db()
        if not db:
            return AgentData(
                name="codex", display_name="CodeX",
                stats={}, raw="CodeX: 未检测到数据库文件"
            )
        try:
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT COUNT(*) as cnt, SUM(tokens_used) as total FROM threads")
            row = cur.fetchone()
            cnt = row["cnt"] or 0
            total = row["total"] or 0
            conn.close()

            stats = {
                "model": "codex-default",
                "total_tokens": total,
                "session_count": cnt,
            }
            raw = (
                f"📊 CodeX\n"
                f"  总 tokens: {fmt_num(total)}\n"
                f"  线程数: {cnt}"
            )
            return AgentData(name="codex", display_name="CodeX", stats=stats, raw=raw)
        except Exception as e:
            return AgentData(
                name="codex", display_name="CodeX",
                stats={}, raw=f"CodeX: 读取失败 — {e}"
            )


# ═══════════════════════════════════════════════════
#  OpenClaw
# ═══════════════════════════════════════════════════

OPENCLAW_DIR = os.path.expanduser("~/ai-testing-lab/openclaw/data")
OPENCLAW_SESSIONS = os.path.join(OPENCLAW_DIR, "agents", "main", "sessions", "sessions.json")


class OpenClawAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "openclaw"

    @staticmethod
    def display_name() -> str:
        return "OpenClaw"

    @staticmethod
    def detect() -> bool:
        return os.path.exists(OPENCLAW_SESSIONS)

    def collect(self) -> AgentData:
        if not os.path.exists(OPENCLAW_SESSIONS):
            return AgentData(
                name="openclaw", display_name="OpenClaw",
                stats={}, raw="OpenClaw: 数据文件不存在"
            )
        try:
            with open(OPENCLAW_SESSIONS, encoding="utf-8") as f:
                data = json.load(f)

            # sessions.json 结构: {"agent:main:main": {sessionObj}, "agent:...": {...}}
            agents = []
            if isinstance(data, dict):
                for agent_key, session in data.items():
                    if isinstance(session, dict):
                        agents.append(session)
            elif isinstance(data, list):
                agents = data

            if not agents:
                return AgentData(
                    name="openclaw", display_name="OpenClaw",
                    stats={}, raw="OpenClaw: 尚无会话"
                )

            total_input = sum(s.get("inputTokens", 0) for s in agents)
            total_output = sum(s.get("outputTokens", 0) for s in agents)
            total_cache = sum(s.get("cacheRead", 0) for s in agents)

            # 找最近活跃的
            latest = max(agents, key=lambda s: s.get("startedAt", 0) or s.get("updatedAt", 0))
            model = latest.get("model", "unknown")
            provider = latest.get("modelProvider", "")
            model_display = f"{model}" if not provider else f"{model} ({provider})"
            context = latest.get("contextTokens", DEFAULT_CONTEXT)

            stats = {
                "model": model,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "cache_read": total_cache,
                "total_tokens": total_input + total_output,
                "context_window": context,
                "agent_count": len(agents),
            }

            # 如果只有 1 个 agent，显示上下文占用
            if len(agents) == 1:
                total = total_input + total_output
                pct = round(total / context * 100, 1) if context else 0
                raw = (
                    f"📊 OpenClaw — {model_display}\n"
                    f"  上下文: {fmt_num(total)}/{fmt_num(context)} ({fmt_pct(pct)})\n"
                    f"  输入: {fmt_num(total_input)} | 输出: {fmt_num(total_output)}\n"
                    f"  缓存读取: {fmt_num(total_cache)}"
                )
            else:
                raw = (
                    f"📊 OpenClaw\n"
                    f"  共 {len(agents)} 个 Agent\n"
                    f"  最新: {model_display}\n"
                    f"  总 tokens: {fmt_num(total_input + total_output)}\n"
                    f"  缓存读取: {fmt_num(total_cache)}"
                )
            return AgentData(name="openclaw", display_name="OpenClaw", stats=stats, raw=raw)
        except Exception as e:
            return AgentData(
                name="openclaw", display_name="OpenClaw",
                stats={}, raw=f"OpenClaw: 读取失败 — {e}"
            )


# ═══════════════════════════════════════════════════
#  Agent 注册表
# ═══════════════════════════════════════════════════

ALL_AGENTS: list[type[BaseAgent]] = [
    HermesAgent,
    ClaudeCodeAgent,
    CodeXAgent,
    OpenClawAgent,
]


def detect_installed() -> list[type[BaseAgent]]:
    """检测当前机器上装了哪些 Agent"""
    return [cls for cls in ALL_AGENTS if cls.detect()]


def get_agent(name: str) -> BaseAgent:
    for cls in ALL_AGENTS:
        if cls.name() == name.lower().strip():
            return cls()
    raise ValueError(f"不支持的 Agent: {name}")


# ═══════════════════════════════════════════════════
#  交互式菜单
# ═══════════════════════════════════════════════════

def show_menu(installed: list[type[BaseAgent]]) -> BaseAgent:
    """显示菜单让用户选择 Agent"""
    print("\n🔍 选择你要监控的 AI 助手：")
    print("─" * 40)
    for i, cls in enumerate(installed, 1):
        print(f"  [{i}] {cls.display_name()}")
    print("  [q] 退出")
    print("─" * 40)

    while True:
        try:
            choice = input("请选择 (1-{})：".format(len(installed))).strip().lower()
            if choice == "q":
                print("再见 👋")
                sys.exit(0)
            idx = int(choice) - 1
            if 0 <= idx < len(installed):
                return installed[idx]()
            print(f"请输入 1-{len(installed)} 或 q")
        except (ValueError, EOFError):
            print(f"请输入 1-{len(installed)} 或 q")


# ═══════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="token-stats — 选个 Agent 看它的消耗",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  token-stats                   交互式选择 Agent → 查看统计
  token-stats -b hermes        直接查看 Hermes
  token-stats --watch          交互式选择 Agent → 实时监控
  token-stats -b codex --watch 直接监控 CodeX
  token-stats --list-backends  查看本机安装了哪些 Agent
  token-stats setup            创建 ~/.local/bin/token-stats 软链
        """,
    )
    parser.add_argument("--version", action="store_true", help="显示版本号")
    parser.add_argument("--list-backends", action="store_true", help="列出本机已安装的 Agent")
    parser.add_argument("-b", "--backend", help="直接指定 Agent: hermes/claude-code/codex/openclaw")
    parser.add_argument("--watch", nargs="?", type=int, const=5, default=None, metavar="秒",
                        help="实时监控模式（默认每 5 秒轮询）")
    parser.add_argument("setup", nargs="?", const=True, help="创建 ~/.local/bin/token-stats 软链")

    args = parser.parse_args()

    # ── version ──
    if args.version:
        print(f"token-stats v{VERSION}")
        return

    # ── setup ──
    if args.setup:
        target = os.path.join(os.path.expanduser("~"), ".local", "bin", "token-stats")
        script_path = os.path.abspath(__file__)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.exists(target):
            current = os.path.realpath(target)
            if current == script_path:
                print(f"✅ 软链已存在: {target} → {script_path}")
                return
            os.remove(target)
        os.symlink(script_path, target)
        print(f"✅ 已创建: {target} → {script_path}")
        # 检查 PATH
        bin_dir = os.path.dirname(target)
        if bin_dir not in os.environ.get("PATH", "").split(":"):
            print(f"⚠️  {bin_dir} 不在 PATH 中，请添加:")
            print(f"   echo 'export PATH=\"$PATH:{bin_dir}\"' >> ~/.zshrc")
            print(f"   source ~/.zshrc")
        return

    # ── list-backends ──
    if args.list_backends:
        installed = detect_installed()
        print("\n本机已安装的 AI 助手：")
        for cls in ALL_AGENTS:
            ok = "✅" if cls.detect() else "❌"
            print(f"  {ok} {cls.display_name()}")
        print()
        return

    # ── 选择 Agent ──
    installed = detect_installed()
    if not installed:
        print("❌ 本机未检测到任何支持的 AI 助手")
        print("   支持的 Agent: Hermes, Claude Code, CodeX, OpenClaw")
        print("   请先使用并运行一个 Agent 后再来查看统计。")
        return

    if args.backend:
        try:
            agent = get_agent(args.backend)
        except ValueError as e:
            print(f"❌ {e}")
            print(f"   可选: {', '.join(cls.name() for cls in ALL_AGENTS)}")
            return
    elif len(installed) == 1:
        agent = installed[0]()
        print(f"\n（本机仅安装了 {agent.display_name()}，直接显示统计）")
    else:
        agent = show_menu(installed)

    # ── 收集并展示 ──
    if args.watch is not None:
        agent.watch(args.watch)
    else:
        try:
            data = agent.collect()
            print()
            print(data.raw)
            print()
        except Exception as e:
            print(f"❌ 获取 {agent.display_name()} 统计失败: {e}")


if __name__ == "__main__":
    main()
