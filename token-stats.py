#!/usr/bin/env python3
"""
token-stats — 跨平台 token 消耗精确统计工具

支持的后端 (Backend):
  hermes       ~/.hermes/state.db (SQLite)              — 会话级累计
  claude-code  ~/.claude/projects/**/*.jsonl (JSONL)    — 消息级 + 子代理级
  openclaw     ~/ai-testing-lab/openclaw/data/ (JSON)   — 会话级 + 消息级 + 轨迹级
  codex        ~/.codex/state_5.sqlite (SQLite)         — 线程级累计
  auto         自动检测可用后端 (默认)

用法:
  # 任务开始
  token-stats --save-baseline
  token-stats --save-baseline --backend claude-code

  # 任务结束
  token-stats --delta
  token-stats --delta --backend claude-code

  # 查看
  token-stats --summary
  token-stats --recent 5
  token-stats --validate

数据溯源:
  所有 token 数据来自 API 服务商返回的 usage 对象，经各 Agent 框架写入本地存储。
  - Hermes:    agent/usage_pricing.py → normalize_usage() → sessions 表
  - Claude:    每条 assistant message 的 usage 字段
  - OpenClaw:  3 层存储 (会话级 sessions.json / 消息级 .jsonl / 轨迹级 trajectory.jsonl)
  - CodeX:     threads 表的 tokens_used 字段
"""

import sqlite3
import json
import os
import sys
import re
import glob
import argparse
import time
import signal
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ═══════════════════════════════════════════════════
#  模型上下文窗口映射表
# ═══════════════════════════════════════════════════

MODEL_CONTEXT_MAP = {
    # DeepSeek
    "deepseek-v4-flash": 1_048_576,
    "deepseek-v4": 1_048_576,
    "deepseek-chat": 1_048_576,
    "deepseek-reasoner": 1_048_576,
    "deepseek-v3": 131_072,
    "deepseek-v2": 131_072,
    # OpenAI
    "gpt-4o": 131_072,
    "gpt-4o-mini": 131_072,
    "gpt-4-turbo": 131_072,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_384,
    "o1": 204_800,
    "o3": 204_800,
    "o4-mini": 1_048_576,
    # Anthropic
    "claude-sonnet-4": 204_800,
    "claude-sonnet-4-6": 204_800,
    "claude-opus-4": 204_800,
    "claude-haiku-3.5": 204_800,
    "claude-3-opus": 204_800,
    "claude-3-sonnet": 204_800,
    "claude-3-haiku": 204_800,
    # Gemini
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.0-flash": 1_048_576,
    "gemini-1.5-pro": 2_097_152,
    # Qwen
    "qwen3": 131_072,
    "qwen3.6": 131_072,
    "qwen-max": 32_768,
    "qwen-plus": 131_072,
    "qwen-turbo": 1_048_576,
    # Llama
    "llama-3.1": 131_072,
    "llama-3": 8_192,
    # Mistral
    "mistral-large": 131_072,
    "mixtral": 32_768,
}

DEFAULT_CONTEXT = 131_072  # 128K 安全默认值


def fmt_num(n: int) -> str:
    """格式化大数字：1234 → 1.2K, 1234567 → 1.2M"""
    if n < 1000:
        return str(n)
    elif n < 1_000_000:
        return f"{n/1000:.1f}K"
    else:
        return f"{n/1_000_000:.2f}M"


def detect_context(model_name: str) -> int:
    """自动检测模型上下文窗口"""
    if not model_name:
        return DEFAULT_CONTEXT
    m = model_name.lower().strip()
    # 精确匹配
    if m in MODEL_CONTEXT_MAP:
        return MODEL_CONTEXT_MAP[m]
    # 前缀匹配（从长到短）
    for key, val in sorted(MODEL_CONTEXT_MAP.items(), key=lambda x: -len(x[0])):
        if m.startswith(key):
            return val
    return DEFAULT_CONTEXT


# ═══════════════════════════════════════════════════
#  通用数据模型
# ═══════════════════════════════════════════════════

@dataclass
class ModelUsage:
    """单个模型的用量"""
    model: str = "unknown"
    api_calls: int = 0        # 本次增量
    api_calls_total: int = 0  # 会话累计
    input_tokens: int = 0
    input_tokens_total: int = 0
    output_tokens: int = 0
    output_tokens_total: int = 0
    cache_read: int = 0
    cache_read_total: int = 0
    sub_calls: int = 0
    sub_calls_total: int = 0

    @property
    def context_window(self) -> int:
        return detect_context(self.model)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def total_tokens_total(self) -> int:
        return self.input_tokens_total + self.output_tokens_total

    @property
    def context_pct(self) -> float:
        return round(self.total_tokens_total / self.context_window * 100, 1) if self.context_window else 0


@dataclass
class TaskStats:
    """一次任务的完整统计"""
    backend: str = "auto"
    models: list[ModelUsage] = field(default_factory=list)
    cumulative_input: int = 0
    cumulative_output: int = 0

    @property
    def total_api_calls(self) -> int:
        return sum(m.api_calls for m in self.models)

    @property
    def total_api_calls_cumulative(self) -> int:
        return sum(m.api_calls_total for m in self.models)

    @property
    def total_input(self) -> int:
        return sum(m.input_tokens for m in self.models)

    @property
    def total_output(self) -> int:
        return sum(m.output_tokens for m in self.models)

    @property
    def total_cumulative(self) -> int:
        return self.cumulative_input + self.cumulative_output

    @property
    def model_count(self) -> int:
        return len(self.models)


# ═══════════════════════════════════════════════════
#  Backend 基类
# ═══════════════════════════════════════════════════

class BackendError(Exception):
    pass


class BaseBackend(ABC):
    """各 Agent 后端的统一接口"""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def save_baseline(self) -> None:
        """保存当前状态为基线"""
        ...

    @abstractmethod
    def get_delta(self) -> TaskStats:
        """返回本次任务统计（含多模型）"""
        ...

    @abstractmethod
    def get_summary(self) -> str:
        """返回当前会话累计摘要"""
        ...

    @abstractmethod
    def validate(self) -> list[str]:
        """返回数据校验问题列表（空=无问题）"""
        ...

    @staticmethod
    def detect() -> bool:
        """检测本后端是否可用"""
        ...

    def watch(self, interval: int = 5) -> None:
        """实时监控模式：每 N 秒轮询一次，输出增量变化。按 Ctrl+C 停止。"""
        running = True

        def _on_signal(sig, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)

        print(f"📡 实时监控 [{self.name()}] — 每 {interval} 秒刷新 (Ctrl+C 停止)\n")
        time.sleep(0.5)

        # 第 1 步：记录初始基线
        self.save_baseline()
        total_delta = TaskStats(backend=self.name(), models=[])
        first = True

        while running:
            time.sleep(interval)
            if not running:
                break

            try:
                delta = self.get_delta()
                # get_delta 删除基线，重新保存以便下一轮使用
                self.save_baseline()
            except BackendError as e:
                print(f"  ⚠️ {e}")
                continue

            # 检查是否有实际变化
            has_change = any(
                m.api_calls > 0 or m.input_tokens > 0 or m.output_tokens > 0
                for m in delta.models
            )

            if has_change:
                now = datetime.now().strftime("%H:%M")
                for m in delta.models:
                    if m.api_calls > 0 or m.input_tokens > 0 or m.output_tokens > 0:
                        tok = m.input_tokens + m.output_tokens
                        inp = m.input_tokens
                        out = m.output_tokens
                        cache = f" · 缓存 {fmt_num(m.cache_read)}" if m.cache_read else ""
                        print(f"  [{now}] 对话 {m.api_calls} 轮 · 消耗 {fmt_num(tok)} tokens ({m.model})")
                        print(f"        输入 {fmt_num(inp)} / 输出 {fmt_num(out)}{cache}")
                        # 累计到 total_delta
                        existing = next((x for x in total_delta.models if x.model == m.model), None)
                        if existing:
                            existing.api_calls += m.api_calls
                            existing.input_tokens += m.input_tokens
                            existing.output_tokens += m.output_tokens
                            existing.cache_read += m.cache_read
                        else:
                            total_delta.models.append(m)
                    total_delta.cumulative_input += sum(m.input_tokens for m in delta.models)
                    total_delta.cumulative_output += sum(m.output_tokens for m in delta.models)
            elif first:
                print("  ⏳ 等待对话...")

            first = False

        # Ctrl+C 停止后输出汇总
        if total_delta.models:
            total_tok = total_delta.cumulative_input + total_delta.cumulative_output
            print(f"\n📊 本次监控汇总")
            for m in total_delta.models:
                tok = m.input_tokens + m.output_tokens
                print(f"  {m.model}: {m.api_calls} 轮 · {fmt_num(tok)} tokens")
            print(f"  ───────────────")
            print(f"  总计: {sum(m.api_calls for m in total_delta.models)} 轮 · {fmt_num(total_tok)} tokens")
        else:
            print("\n📭 监控期间没有检测到对话")


# ═══════════════════════════════════════════════════
#  Hermes Backend
# ═══════════════════════════════════════════════════

HERMES_DB = os.path.expanduser("~/.hermes/state.db")
HERMES_BASELINE = os.path.expanduser("~/.hermes/.task_baseline.json")


class HermesBackend(BaseBackend):
    def name(self) -> str:
        return "hermes"

    def _get_conn(self):
        if not os.path.exists(HERMES_DB):
            raise BackendError(f"Hermes 数据库不存在: {HERMES_DB}")
        conn = sqlite3.connect(HERMES_DB)
        conn.row_factory = sqlite3.Row
        return conn

    def _current_session(self, conn):
        cur = conn.execute("SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1")
        r = cur.fetchone()
        if not r:
            raise BackendError("Hermes 中没有找到任何会话记录")
        return r["id"]

    def _session_stats(self, conn, sid):
        cur = conn.execute("""
            SELECT id, input_tokens, output_tokens, cache_read_tokens,
                   cache_write_tokens, reasoning_tokens, api_call_count,
                   tool_call_count, model, title
            FROM sessions WHERE id = ?
        """, (sid,))
        r = cur.fetchone()
        if not r:
            raise BackendError(f"会话不存在: {sid}")
        return r

    def save_baseline(self) -> None:
        conn = self._get_conn()
        sid = self._current_session(conn)
        stats = self._session_stats(conn, sid)
        baseline = {
            "session_id": sid,
            "input_tokens": stats["input_tokens"] or 0,
            "output_tokens": stats["output_tokens"] or 0,
            "cache_read_tokens": stats["cache_read_tokens"] or 0,
            "api_call_count": stats["api_call_count"] or 0,
            "tool_call_count": stats["tool_call_count"] or 0,
            "model": stats["model"] or "unknown",
            "timestamp": datetime.now().isoformat(),
        }
        with open(HERMES_BASELINE, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)

    def get_delta(self) -> TaskStats:
        if not os.path.exists(HERMES_BASELINE):
            raise BackendError(
                "未找到基线文件，请先运行 --save-baseline\n"
                f"  预期路径: {HERMES_BASELINE}"
            )
        with open(HERMES_BASELINE, encoding="utf-8") as f:
            bl = json.load(f)

        conn = self._get_conn()
        sid = self._current_session(conn)
        stats = self._session_stats(conn, sid)

        if stats["id"] != bl["session_id"]:
            raise BackendError(
                "会话已变更，需重新 --save-baseline\n"
                f"  基线: {bl['session_id'][:20]} → 当前: {stats['id'][:20]}"
            )

        model = stats["model"] or bl.get("model", "unknown")
        delta = ModelUsage(
            model=model,
            api_calls=(stats["api_call_count"] or 0) - (bl["api_call_count"] or 0),
            api_calls_total=stats["api_call_count"] or 0,
            input_tokens=(stats["input_tokens"] or 0) - (bl["input_tokens"] or 0),
            input_tokens_total=stats["input_tokens"] or 0,
            output_tokens=(stats["output_tokens"] or 0) - (bl["output_tokens"] or 0),
            output_tokens_total=stats["output_tokens"] or 0,
            cache_read=(stats["cache_read_tokens"] or 0) - (bl["cache_read_tokens"] or 0),
            cache_read_total=stats["cache_read_tokens"] or 0,
        )

        # 校验负数
        for name, val in [("api_calls", delta.api_calls), ("input_tokens", delta.input_tokens),
                          ("output_tokens", delta.output_tokens)]:
            if val < 0:
                raise BackendError(
                    f"数据异常: {name} 增量为 {val}，请重新 --save-baseline"
                )

        os.remove(HERMES_BASELINE)

        return TaskStats(
            backend="hermes",
            models=[delta],
            cumulative_input=stats["input_tokens"] or 0,
            cumulative_output=stats["output_tokens"] or 0,
        )

    def get_summary(self) -> str:
        conn = self._get_conn()
        sid = self._current_session(conn)
        stats = self._session_stats(conn, sid)
        model = stats["model"] or "unknown"
        cw = detect_context(model)
        total = (stats["input_tokens"] or 0) + (stats["output_tokens"] or 0)
        pct = round(total / cw * 100, 1)
        return f"Hermes | {model} | {total:,}/{cw:,} tokens ({pct}%) | {stats['api_call_count']} calls"

    def validate(self) -> list[str]:
        issues = []
        if not os.path.exists(HERMES_DB):
            issues.append(f"Hermes 数据库不存在: {HERMES_DB}")
            return issues
        try:
            conn = self._get_conn()
            stats = self._session_stats(conn, self._current_session(conn))
            if (stats["api_call_count"] or 0) > 0 and (stats["input_tokens"] or 0) == 0 and (stats["output_tokens"] or 0) == 0:
                issues.append("存在 API 调用但 tokens 为 0，框架可能未正确写入 usage")
        except BackendError as e:
            issues.append(str(e))
        return issues

    @staticmethod
    def detect() -> bool:
        return os.path.exists(HERMES_DB)


# ═══════════════════════════════════════════════════
#  Claude Code Backend
# ═══════════════════════════════════════════════════

CLAUDE_DIR = os.path.expanduser("~/.claude")
CLAUDE_BASELINE = os.path.expanduser("~/.claude/.token_baseline.json")


class ClaudeCodeBackend(BaseBackend):
    def name(self) -> str:
        return "claude-code"

    def _find_sessions(self):
        """查找所有可用的 Claude Code 会话 JSONL 文件"""
        projects_dir = os.path.join(CLAUDE_DIR, "projects")
        if not os.path.isdir(projects_dir):
            raise BackendError(f"Claude Code 项目目录不存在: {projects_dir}")
        session_files = []
        for proj in os.listdir(projects_dir):
            proj_dir = os.path.join(projects_dir, proj)
            if not os.path.isdir(proj_dir):
                continue
            for fname in os.listdir(proj_dir):
                if fname.endswith(".jsonl") and not fname.endswith(".trajectory.jsonl"):
                    fpath = os.path.join(proj_dir, fname)
                    session_files.append((proj, fname, fpath))
        return sorted(session_files, key=lambda x: os.path.getmtime(x[2]), reverse=True)

    def _parse_session(self, fpath: str) -> list[ModelUsage]:
        """解析单个 JSONL 文件，按模型汇总 usage"""
        model_usages: dict[str, ModelUsage] = {}
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 主模型调用: type == "assistant"
                if msg.get("type") == "assistant":
                    model = msg.get("message", {}).get("model") or msg.get("model", "unknown")
                    # 跳过合成模型（如 <synthetic>）
                    if model.startswith("<"):
                        continue
                    usage = msg.get("message", {}).get("usage") or msg.get("usage", {})
                    if model not in model_usages:
                        model_usages[model] = ModelUsage(model=model)
                    mu = model_usages[model]
                    mu.api_calls_total += 1
                    mu.input_tokens_total += usage.get("input_tokens", 0)
                    mu.output_tokens_total += usage.get("output_tokens", 0)
                    mu.cache_read_total += usage.get("cache_read_input_tokens", 0)

                # 子代理调用: toolUseResult.usage
                tool_result = msg.get("toolUseResult")
                if tool_result and "usage" in tool_result:
                    # 子代理没有直接记录 model 名，标记为 "subagent"
                    if "__subagent__" not in model_usages:
                        model_usages["__subagent__"] = ModelUsage(model="subagent")
                    su = model_usages["__subagent__"]
                    su.sub_calls_total += 1
                    sub_usage = tool_result["usage"]
                    su.input_tokens_total += sub_usage.get("input_tokens", 0)
                    su.output_tokens_total += sub_usage.get("output_tokens", 0)
                    su.cache_read_total += sub_usage.get("cache_read_input_tokens", 0)

        return list(model_usages.values())

    def _latest_session_path(self) -> Optional[str]:
        sessions = self._find_sessions()
        return sessions[0][2] if sessions else None

    def save_baseline(self) -> None:
        latest = self._latest_session_path()
        if not latest:
            raise BackendError("Claude Code 中没有找到任何会话文件")
        usages = self._parse_session(latest)
        baseline = {
            "session_path": latest,
            "models": {mu.model: {
                "api_calls_total": mu.api_calls_total,
                "input_tokens_total": mu.input_tokens_total,
                "output_tokens_total": mu.output_tokens_total,
                "cache_read_total": mu.cache_read_total,
                "sub_calls_total": mu.sub_calls_total,
            } for mu in usages},
            "timestamp": datetime.now().isoformat(),
        }
        os.makedirs(os.path.dirname(CLAUDE_BASELINE), exist_ok=True)
        with open(CLAUDE_BASELINE, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)

    def get_delta(self) -> TaskStats:
        if not os.path.exists(CLAUDE_BASELINE):
            raise BackendError(
                "未找到 Claude Code 基线文件\n"
                f"  预期路径: {CLAUDE_BASELINE}\n"
                "  请先运行: token-stats --save-baseline --backend claude-code"
            )
        with open(CLAUDE_BASELINE, encoding="utf-8") as f:
            bl = json.load(f)

        # 使用最新的会话文件
        latest = self._latest_session_path()
        if not latest:
            raise BackendError("Claude Code 中没有找到任何会话文件")

        # 如果会话文件变了，尝试匹配
        if latest != bl["session_path"]:
            # 可能是新会话，尝试从同一项目目录找
            pass  # 继续用最新会话

        current_usages = self._parse_session(latest)
        bl_models = bl.get("models", {})

        models = []
        cum_input = 0
        cum_output = 0

        for mu in current_usages:
            bl_m = bl_models.get(mu.model, {})
            mu.api_calls = mu.api_calls_total - bl_m.get("api_calls_total", 0)
            mu.input_tokens = mu.input_tokens_total - bl_m.get("input_tokens_total", 0)
            mu.output_tokens = mu.output_tokens_total - bl_m.get("output_tokens_total", 0)
            mu.cache_read = mu.cache_read_total - bl_m.get("cache_read_total", 0)
            mu.sub_calls = mu.sub_calls_total - bl_m.get("sub_calls_total", 0)
            cum_input += mu.input_tokens_total
            cum_output += mu.output_tokens_total
            models.append(mu)

        # 检查基线中存在的模型但当前文件中没有（理论上不应出现）
        for bl_model_name in bl_models:
            if not any(m.model == bl_model_name for m in models):
                models.append(ModelUsage(
                    model=bl_model_name,
                    api_calls=0,
                    api_calls_total=bl_models[bl_model_name].get("api_calls_total", 0),
                    input_tokens=0,
                    input_tokens_total=bl_models[bl_model_name].get("input_tokens_total", 0),
                    output_tokens=0,
                    output_tokens_total=bl_models[bl_model_name].get("output_tokens_total", 0),
                ))

        if os.path.exists(CLAUDE_BASELINE):
            os.remove(CLAUDE_BASELINE)

        return TaskStats(backend="claude-code", models=models, cumulative_input=cum_input, cumulative_output=cum_output)

    def get_summary(self) -> str:
        latest = self._latest_session_path()
        if not latest:
            return "Claude Code: 没有找到任何会话文件"
        usages = self._parse_session(latest)
        total_in = sum(m.input_tokens_total for m in usages)
        total_out = sum(m.output_tokens_total for m in usages)
        total_calls = sum(m.api_calls_total for m in usages)
        models_str = ", ".join(f"{m.model}({m.api_calls_total})" for m in usages if m.model != "__subagent__")
        return f"Claude Code | {models_str} | 共{total_calls}次调用 | {total_in+total_out:,} tokens"

    def validate(self) -> list[str]:
        issues = []
        if not os.path.isdir(os.path.join(CLAUDE_DIR, "projects")):
            issues.append(f"Claude Code 项目目录不存在: {os.path.join(CLAUDE_DIR, 'projects')}")
            return issues
        sessions = self._find_sessions()
        if not sessions:
            issues.append("Claude Code 中没有找到任何会话文件")
        return issues

    @staticmethod
    def detect() -> bool:
        return os.path.isdir(os.path.join(CLAUDE_DIR, "projects"))


# ═══════════════════════════════════════════════════
#  OpenClaw Backend
# ═══════════════════════════════════════════════════

OPENCLAW_DIR = os.path.expanduser("~/ai-testing-lab/openclaw/data")
OPENCLAW_SESSIONS = os.path.join(OPENCLAW_DIR, "agents", "main", "sessions", "sessions.json")


class OpenClawBackend(BaseBackend):
    def name(self) -> str:
        return "openclaw"

    def _read_sessions_index(self) -> dict:
        if not os.path.exists(OPENCLAW_SESSIONS):
            raise BackendError(f"OpenClaw 会话索引不存在: {OPENCLAW_SESSIONS}")
        with open(OPENCLAW_SESSIONS, encoding="utf-8") as f:
            return json.load(f)

    def _get_latest_session(self):
        idx = self._read_sessions_index()
        sessions = idx.get("sessions", []) if isinstance(idx, dict) else idx if isinstance(idx, list) else []
        if not sessions:
            raise BackendError("OpenClaw 中没有找到任何会话")
        # 按最后活动时间排序
        latest = max(sessions, key=lambda s: s.get("lastActivityAt", 0) if isinstance(s, dict) else 0)
        return latest

    def save_baseline(self) -> None:
        latest = self._get_latest_session()
        sid = latest.get("id", "unknown") if isinstance(latest, dict) else str(latest)
        bl_path = os.path.join(OPENCLAW_DIR, ".baseline.json")
        baseline = {
            "session_id": sid,
            "input_tokens": latest.get("inputTokens", 0) if isinstance(latest, dict) else 0,
            "output_tokens": latest.get("outputTokens", 0) if isinstance(latest, dict) else 0,
            "cache_read": latest.get("cacheRead", 0) if isinstance(latest, dict) else 0,
            "timestamp": datetime.now().isoformat(),
        }
        with open(bl_path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2)

    def get_delta(self) -> TaskStats:
        bl_path = os.path.join(OPENCLAW_DIR, ".baseline.json")
        if not os.path.exists(bl_path):
            raise BackendError("未找到 OpenClaw 基线文件")
        with open(bl_path, encoding="utf-8") as f:
            bl = json.load(f)

        latest = self._get_latest_session()
        l_input = latest.get("inputTokens", 0) if isinstance(latest, dict) else 0
        l_output = latest.get("outputTokens", 0) if isinstance(latest, dict) else 0
        l_cache = latest.get("cacheRead", 0) if isinstance(latest, dict) else 0

        model = (latest.get("model", "unknown") if isinstance(latest, dict) else "unknown") if isinstance(latest, dict) else "unknown"
        sub_calls = latest.get("subagentCalls", 0) if isinstance(latest, dict) else 0

        mu = ModelUsage(
            model=model,
            input_tokens=l_input - bl.get("input_tokens", 0),
            input_tokens_total=l_input,
            output_tokens=l_output - bl.get("output_tokens", 0),
            output_tokens_total=l_output,
            cache_read=l_cache - bl.get("cache_read", 0),
            cache_read_total=l_cache,
            sub_calls=sub_calls,
            sub_calls_total=sub_calls,
        )

        if os.path.exists(bl_path):
            os.remove(bl_path)

        return TaskStats(backend="openclaw", models=[mu], cumulative_input=l_input, cumulative_output=l_output)

    def get_summary(self) -> str:
        try:
            latest = self._get_latest_session()
        except BackendError:
            return "OpenClaw: 无会话"
        l_input = latest.get("inputTokens", 0) if isinstance(latest, dict) else 0
        l_output = latest.get("outputTokens", 0) if isinstance(latest, dict) else 0
        model = latest.get("model", "unknown") if isinstance(latest, dict) else "unknown"
        return f"OpenClaw | {model} | {l_input+l_output:,} tokens"

    def validate(self) -> list[str]:
        issues = []
        if not os.path.isdir(OPENCLAW_DIR):
            issues.append(f"OpenClaw 目录不存在: {OPENCLAW_DIR}")
        elif not os.path.exists(OPENCLAW_SESSIONS):
            issues.append(f"OpenClaw 会话索引不存在: {OPENCLAW_SESSIONS}")
        return issues

    @staticmethod
    def detect() -> bool:
        return os.path.exists(OPENCLAW_SESSIONS)


# ═══════════════════════════════════════════════════
#  CodeX Backend
# ═══════════════════════════════════════════════════

CODEX_DB = None  # 在 detect() 中动态检测
CODEX_BASELINE = os.path.expanduser("~/.codex/.baseline.json")


def _find_codex_db() -> Optional[str]:
    """动态查找 CodeX 数据库文件（支持 state_*.sqlite 版本变化）"""
    codex_dir = os.path.expanduser("~/.codex")
    if not os.path.isdir(codex_dir):
        return None
    # 按文件名排序取最新
    dbs = sorted(
        [f for f in os.listdir(codex_dir) if re.match(r'^state_\d+\.sqlite$', f)],
        reverse=True
    )
    return os.path.join(codex_dir, dbs[0]) if dbs else None


class CodeXBackend(BaseBackend):
    def name(self) -> str:
        return "codex"

    def _get_conn(self):
        db = _find_codex_db()
        if not db:
            raise BackendError("CodeX 数据库不存在（未找到 ~/.codex/state_*.sqlite）")
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        return conn

    def _check_codex_dir(self) -> bool:
        codex_dir = os.path.expanduser("~/.codex")
        return os.path.isdir(codex_dir) and _find_codex_db() is not None

    def _latest_thread(self, conn):
        cur = conn.execute("SELECT id, tokens_used FROM threads ORDER BY id DESC LIMIT 1")
        r = cur.fetchone()
        if not r:
            raise BackendError("CodeX 中没有找到任何线程")
        return r

    def save_baseline(self) -> None:
        conn = self._get_conn()
        thread = self._latest_thread(conn)
        baseline = {
            "thread_id": thread["id"],
            "tokens_used": thread["tokens_used"] or 0,
            "timestamp": datetime.now().isoformat(),
        }
        with open(CODEX_BASELINE, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2)

    def get_delta(self) -> TaskStats:
        if not os.path.exists(CODEX_BASELINE):
            raise BackendError("未找到 CodeX 基线文件")
        with open(CODEX_BASELINE, encoding="utf-8") as f:
            bl = json.load(f)
        conn = self._get_conn()
        thread = self._latest_thread(conn)
        current_tokens = thread["tokens_used"] or 0
        delta_tokens = current_tokens - bl.get("tokens_used", 0)
        mu = ModelUsage(
            model="codex-default",
            input_tokens=delta_tokens,
            input_tokens_total=current_tokens,
        )
        if os.path.exists(CODEX_BASELINE):
            os.remove(CODEX_BASELINE)
        return TaskStats(backend="codex", models=[mu], cumulative_input=current_tokens, cumulative_output=0)

    def get_summary(self) -> str:
        try:
            conn = self._get_conn()
            thread = self._latest_thread(conn)
            return f"CodeX | {thread['tokens_used']:,} tokens"
        except BackendError:
            return "CodeX: 无数据"

    def validate(self) -> list[str]:
        issues = []
        if not _find_codex_db():
            issues.append("CodeX 数据库不存在（未找到 ~/.codex/state_*.sqlite）")
        return issues

    @staticmethod
    def detect() -> bool:
        return _find_codex_db() is not None


# ═══════════════════════════════════════════════════
#  Auto Backend — 自动检测
# ═══════════════════════════════════════════════════

BACKENDS: list[type[BaseBackend]] = [
    HermesBackend,
    ClaudeCodeBackend,
    OpenClawBackend,
    CodeXBackend,
]


def auto_detect() -> BaseBackend:
    """按优先级自动检测可用的后端"""
    for cls in BACKENDS:
        if cls.detect():
            return cls()
    raise BackendError(
        "未检测到任何受支持的 Agent 工具。\n"
        "支持的 Agent: hermes, claude-code, openclaw, codex\n"
        "请先确保至少一个 Agent 有数据文件，或使用 --backend 手动指定。"
    )


def get_backend(name: str) -> BaseBackend:
    name = name.lower().strip()
    for cls in BACKENDS:
        b = cls()
        if b.name() == name:
            return b
    raise BackendError(f"不支持的后端: {name}。可选: {', '.join(b().name() for b in BACKENDS)}")


# ═══════════════════════════════════════════════════
#  Table Formatter
# ═══════════════════════════════════════════════════

def format_table(stats: TaskStats) -> str:
    """生成紧凑表格（方案 B 风格）"""

    if not stats.models:
        return "📊 本次任务统计\n  (无数据)"

    # 过滤噪音模型（<synthetic>、__subagent__ 等只合并到总数）
    main_models = [m for m in stats.models if not m.model.startswith("<") and m.model != "__subagent__"]
    sub_models = [m for m in stats.models if m.model == "__subagent__"]
    other_models = [m for m in stats.models if m.model.startswith("<")]

    # ── 列宽计算 ──
    max_model_len = max((len(m.model) for m in main_models), default=8)
    model_col = max(max_model_len, 8)

    def fmt_xy(x, y):
        """格式化为 X/Y，右对齐数值"""
        xs = f"{x:,}"
        ys = f"{y:,}"
        return f"{xs:>8}/{ys:<8}"

    def fmt_short(n):
        """友好显示大数字: 1.2K, 3.4M"""
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)

    def fmt_pct(mu: ModelUsage) -> str:
        pct = mu.context_pct
        # 跨会话累计可能超过 100%
        if pct >= 100:
            return " >100%"
        if pct >= 90:
            return f" {pct:>4.1f}%🚨"
        elif pct >= 60:
            return f" {pct:>4.1f}%⚠️"
        else:
            return f" {pct:>4.1f}%✅"

    # ── 构建主模型行 ──
    rows = []
    for mu in main_models:
        label = f" {mu.model:<{model_col}} "
        calls = fmt_xy(mu.api_calls, mu.api_calls_total)
        inp = fmt_xy(mu.input_tokens, mu.input_tokens_total)
        out = fmt_xy(mu.output_tokens, mu.output_tokens_total)
        cache = f" {fmt_short(mu.cache_read):>7}/{fmt_short(mu.cache_read_total):<7} "
        pct_s = fmt_pct(mu)
        rows.append(f"│{label}│{calls}│{inp}│{out}│{cache}│{pct_s}│")

    # 子代理行
    for su in sub_models:
        label = f" ⬇subagent{'':<{model_col-10}} "
        calls = fmt_xy(su.sub_calls, su.sub_calls_total)
        inp = fmt_xy(su.input_tokens, su.input_tokens_total)
        out = fmt_xy(su.output_tokens, su.output_tokens_total)
        cache = f" {fmt_short(su.cache_read):>7}/{fmt_short(su.cache_read_total):<7} "
        pct_s = fmt_pct(su)
        rows.append(f"│{label}│{calls}│{inp}│{out}│{cache}│{pct_s}│")

    # ── 分隔线 ──
    sep = "├" + "─" * (model_col + 2) + "┼" + "─" * 19 + "┼" + "─" * 19 + "┼" + "─" * 19 + "┼" + "─" * 17 + "┼" + "─" * 11 + "┤"
    hdr_sep = "├" + "─" * (model_col + 2) + "┬" + "─" * 19 + "┬" + "─" * 19 + "┬" + "─" * 19 + "┬" + "─" * 17 + "┬" + "─" * 11 + "┤"

    # ── 标题行 ──
    total_width = model_col + 2 + 19 + 19 + 19 + 17 + 11 + 6  # +6 for borders
    title_pad = (total_width - 14) // 2
    title = f"┌{'─' * (total_width - 2)}┐"
    title += f"\n│{' ' * title_pad}📊 本次任务统计{' ' * (total_width - 14 - title_pad)}│"

    # 列标题
    col_hdr = f"│ {'模型':^{model_col}} │ {'调用次数':^17} │ {'输入 tokens':^17} │ {'输出 tokens':^17} │ {'Cache':^15} │ {'占用':^9} │"

    # ── 底部 ──
    total_calls = f"{stats.total_api_calls}/{stats.total_api_calls_cumulative}"
    total_tok = f"{stats.total_input + stats.total_output:,}"

    # 累计上下文
    if main_models:
        cw = main_models[0].context_window
        total_cum = stats.cumulative_input + stats.cumulative_output
        ctx_pct = round(total_cum / cw * 100, 1) if cw else 0
        if ctx_pct >= 100:
            ctx_flag = ">100%"
        elif ctx_pct >= 90:
            ctx_flag = f"{ctx_pct}%🚨"
        elif ctx_pct >= 60:
            ctx_flag = f"{ctx_pct}%⚠️"
        else:
            ctx_flag = f"{ctx_pct}%✅"
        ctx_str = f" 累计: {total_cum:,}/{cw:,} tokens ({ctx_flag})"
    else:
        ctx_str = ""

    sub_str = ""
    if sub_models:
        su = sub_models[0]
        sub_str = f" · 子代理: {su.sub_calls}/{su.sub_calls_total}"

    bottom = f"└{'─' * (total_width - 2)}┘"
    bottom += f"\n 🗂  {stats.backend} · {total_calls} 次调用 · {total_tok} tokens{sub_str}"
    bottom += f"\n 📦 {ctx_str}" if ctx_str else ""

    return f"{title}\n{hdr_sep}\n{col_hdr}\n{sep}\n" + "\n".join(rows) + f"\n{bottom}"


# ═══════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="token-stats — 跨平台 token 消耗精确统计",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  token-stats --save-baseline                    # Hermes 任务开始
  token-stats --delta                            # Hermes 任务结束
  token-stats --save-baseline -b claude-code     # Claude Code 任务开始
  token-stats --delta -b claude-code             # Claude Code 任务结束
  token-stats --summary                          # 累计查看
  token-stats --validate                         # 数据完整性验证
  token-stats --list-backends                    # 列出可用后端
        """,
    )
    parser.add_argument("--save-baseline", action="store_true", help="记录基线")
    parser.add_argument("--delta", action="store_true", help="输出本次任务统计")
    parser.add_argument("--summary", action="store_true", help="输出累计摘要")
    parser.add_argument("--validate", action="store_true", help="数据完整性验证")
    parser.add_argument("--list-backends", action="store_true", help="列出可用后端")
    parser.add_argument("-b", "--backend", default="auto", help="后端: hermes/claude-code/openclaw/codex/auto")
    parser.add_argument("--recent", type=int, help="最近 N 条会话")
    parser.add_argument("--version", action="store_true", help="显示版本号")
    parser.add_argument("--watch", nargs="?", type=int, const=5, default=None, metavar="秒",
                        help="实时监控模式（默认每 5 秒轮询）")

    args = parser.parse_args()

    # ── 列出后端 ──
    if args.list_backends:
        print("可用的后端:")
        for cls in BACKENDS:
            b = cls()
            ok = "✅" if b.detect() else "❌"
            print(f"  {ok} {b.name():<15} {b.__class__.__doc__ or ''}")
        return

    # ── 版本号 ──
    VERSION = "1.4.0"
    if args.version:
        print(f"token-stats v{VERSION}")
        return

    # ── 选择后端 ──
    try:
        if args.backend == "auto":
            backend = auto_detect()
        else:
            backend = get_backend(args.backend)
    except BackendError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # ── 验证 ──
    if args.validate:
        issues = backend.validate()
        if issues:
            print(f"🔍 {backend.name()} 数据验证:")
            for iss in issues:
                print(f"  ⚠️ {iss}")
            print("  数据源信息: 请确保 Agent 已正确记录 API 返回的 usage 数据")
        else:
            print(f"🔍 {backend.name()} 数据验证: ✅ 通过")
        return

    # ── 保存基线 ──
    if args.save_baseline:
        try:
            backend.save_baseline()
            print(f"✅ [{backend.name()}] 基线已保存")
        except BackendError as e:
            print(f"❌ [{backend.name()}] {e}")
            sys.exit(1)
        return

    # ── Delta ──
    if args.delta:
        try:
            stats = backend.get_delta()
            print(format_table(stats))
        except BackendError as e:
            print(f"❌ [{backend.name()}] {e}")
            sys.exit(1)
        return

    # ── 摘要 ──
    if args.summary:
        try:
            print(backend.get_summary())
        except BackendError as e:
            print(f"❌ [{backend.name()}] {e}")
            sys.exit(1)
        return

    # ── 实时监控 ──
    if args.watch is not None:
        try:
            backend.watch(interval=args.watch)
        except KeyboardInterrupt:
            print("\n👋 监控已停止")
        except BackendError as e:
            print(f"❌ [{backend.name()}] {e}")
            sys.exit(1)
        return

    # ── 默认: 显示当前状态 + 使用提示 ──
    try:
        print(f"🔄 当前后端: {backend.name()}")
        print(backend.get_summary())
    except BackendError:
        print(f"🔄 当前后端: {backend.name()} (无数据)")
    print()
    print("用法: token-stats --save-baseline  开始任务")
    print("      token-stats --delta          结束任务")
    print("      token-stats --help           查看更多")


if __name__ == "__main__":
    main()
