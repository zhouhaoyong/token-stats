#!/usr/bin/env python3
"""
token-stats — 选个 Agent 看它的 token 消耗

用法:
  token-stats                    交互式菜单：选 Agent → 看统计
  token-stats -a hermes          直接查看 Hermes
  token-stats --watch            交互式菜单 → 实时监控
  token-stats --all              查看本机所有 Agent 的统计
  token-stats -a hermes --now    同默认（显式快照）

  时间段查询:
  token-stats -a hermes --today
  token-stats -a hermes --yesterday
  token-stats -a hermes --week
  token-stats -a hermes --last-7d
  token-stats -a hermes --from 2025-01-01 --to 2025-01-31

  导出:
  token-stats -a hermes --export
  token-stats -a hermes --today --export

  对比:
  token-stats -a hermes --compare --a today --b yesterday
  token-stats -a hermes --compare --a this-week --b last-week
  token-stats -a hermes --compare --a 2025-01-01 --b 2025-01-15
  token-stats -a hermes --compare --a 2025-01-01~2025-01-07 --b 2025-01-08~2025-01-14

  详细模式:
  token-stats -a hermes --detail

安装:
  clawhub install agent-usage-stats
  token-stats setup              创建全局命令并自动加入 PATH
  token-stats --uninstall         删除全局命令并清理 PATH
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import signal
import sqlite3
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

VERSION = "2.3.6"

# 强制 stdout 行缓冲 + UTF-8，使 --watch 模式的输出实时可见
try:
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
except Exception:
    try:
        sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    except Exception:
        pass

# ── WSL 兼容 ──
# Windows 上 WSL2 中运行的 Agent 数据可通过 \\wsl$\ 访问

_WSL_HOMES_CACHE = None


def _get_wsl_homes():
    """Windows 上枚举 WSL 发行版中可能存放 Agent 数据的 home 目录。返回路径列表（缓存结果）。"""
    global _WSL_HOMES_CACHE
    if _WSL_HOMES_CACHE is not None:
        return _WSL_HOMES_CACHE
    if sys.platform != "win32":
        _WSL_HOMES_CACHE = []
        return []
    homes = []

    # 方式 1：wsl.exe 枚举（最可靠，UNC 目录列表在某些机器上不通）
    try:
        import subprocess
        distros_out = subprocess.run(
            ["wsl.exe", "-l", "-q"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
        )
        # wsl.exe 自身输出为 UTF-16LE
        for line in distros_out.stdout.decode("utf-16-le", errors="ignore").splitlines():
            distro = line.strip()
            if not distro:
                continue
            try:
                home_out = subprocess.run(
                    ["wsl.exe", "-d", distro, "--", "bash", "-c", "echo $HOME"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
                )
                # bash 命令输出为 UTF-8
                wsl_home = home_out.stdout.decode("utf-8", errors="ignore").strip()
                if wsl_home and wsl_home.startswith("/"):
                    homes.append(f"//wsl.localhost/{distro}{wsl_home}")
            except Exception:
                pass
    except Exception:
        pass

    # 方式 2：UNC 路径直接枚举（回退，某些机器上更快）
    if not homes:
        for wsl_root in [r"\\wsl.localhost", r"\\wsl$"]:
            try:
                for distro in os.listdir(wsl_root):
                    distro_dir = os.path.join(wsl_root, distro)
                    if not os.path.isdir(distro_dir):
                        continue
                    for sub in ["home", "root"]:
                        home_base = os.path.join(distro_dir, sub)
                        if os.path.isdir(home_base):
                            try:
                                for user in os.listdir(home_base):
                                    uh = os.path.join(home_base, user)
                                    if os.path.isdir(uh):
                                        homes.append(uh)
                            except (OSError, PermissionError):
                                pass
            except (OSError, PermissionError, FileNotFoundError):
                continue

    # 统一为正斜杠格式，Windows 下 Python 访问 WSL UNC 路径需要 /
    homes = [h.replace("\\", "/") for h in homes]
    _WSL_HOMES_CACHE = homes
    return homes


def _resolve_path(relative_path):
    """解析路径：先查本机 ~，再查 WSL home（Windows + wsl.exe 探测），返回首个存在的路径。"""
    native = os.path.join(os.path.expanduser("~"), relative_path)
    if os.path.exists(native):
        return native
    for wh in _get_wsl_homes():
        wp = os.path.join(wh, relative_path)
        if os.path.exists(wp):
            return wp
        # UNC 不通时，通过 wsl.exe 探测文件是否存在
        if sys.platform == "win32":
            try:
                import subprocess
                parts = wh.replace("\\", "/").strip("/").split("/")
                # wh = //wsl.localhost/Distro/home/user
                if len(parts) >= 4 and parts[0] in ("wsl.localhost", "wsl$"):
                    distro = parts[1]
                    wsl_path = "/" + "/".join(parts[3:]) + "/" + relative_path.lstrip(".")
                    probe = subprocess.run(
                        ["wsl.exe", "-d", distro, "--", "test", "-e", wsl_path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3,
                    )
                    if probe.returncode == 0:
                        return wp  # 文件在 WSL 中存在，返回 UNC 路径
            except Exception:
                pass
    return native


def _wsl_unc_to_linux(unc_path):
    """WSL UNC 路径 → (distro, linux_path)。非 WSL 返回 (None, None)。"""
    p = unc_path.replace("\\", "/")
    for prefix in ("//wsl.localhost/", "//wsl$/"):
        if p.startswith(prefix):
            rest = p[len(prefix):]
            idx = rest.find("/")
            if idx > 0:
                return rest[:idx], "/" + rest[idx + 1:]
    return None, None


def _hermes_collect_via_wsl(db_path, from_ts=None, to_ts=None):
    """通过 wsl.exe 在 WSL 内查询 Hermes 数据库。返回 dict 或 None。"""
    import subprocess
    distro, linux_path = _wsl_unc_to_linux(db_path)
    if not distro:
        return None
    # 时间筛选（含 grace 期防止旧会话 ended_at=NULL 被误纳入）
    where = ""
    if from_ts or to_ts:
        parts = []
        if from_ts:
            grace = from_ts - 86400
            parts.append(f"(started_at >= {from_ts} OR (ended_at IS NULL AND started_at >= {grace}) OR ended_at >= {from_ts})")
        if to_ts:
            parts.append(f"started_at <= {to_ts}")
        where = " WHERE " + " AND ".join(parts)
    script = (
        "import sqlite3,json;c=sqlite3.connect(r'%s');c.row_factory=sqlite3.Row;"
        "cols={r[1] for r in c.execute('PRAGMA table_info(sessions)')};"
        "has_ac='api_call_count' in cols;has_tc='tool_call_count' in cols;"
        "ac='api_call_count' if has_ac else '0';tc='tool_call_count' if has_tc else '0';"
        "rows=[dict(r) for r in c.execute("
        "f'SELECT model,SUM(input_tokens) inp,SUM(output_tokens) out,SUM(cache_read_tokens) cache,'"
        "f'SUM('+ac+') calls,SUM('+tc+') tools,COUNT(*) cnt FROM sessions%s GROUP BY model')];"
        "sc=c.execute('SELECT COUNT(*) FROM sessions%s').fetchone()[0];"
        "c.close();print(json.dumps({'rows':rows,'sc':sc},default=str))"
    ) % (linux_path, where, where)
    try:
        r = subprocess.run(
            ["wsl.exe", "-d", distro, "--", "python3", "-c", script],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15,
        )
        return json.loads(r.stdout.decode("utf-8", errors="ignore"))
    except Exception:
        return None, 0


# ── 路径配置系统 ──
# 支持 setup 时自动检测 Agent 路径，保存到配置文件
# 运行时优先读取配置，无配置时回退到标准路径

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "token-stats")
CONFIG_FILE = os.path.join(CONFIG_DIR, "paths.json")


def _load_agent_paths() -> dict:
    """加载已保存的 Agent 数据路径配置"""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_agent_paths(paths: dict):
    """保存 Agent 数据路径配置"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(paths, f, indent=2, ensure_ascii=False)


def _scan_all_agent_paths() -> dict:
    """扫描本机所有 Agent 的数据路径（含 WSL），返回 {agent_name: data_path}"""
    homes = [os.path.expanduser("~")] + _get_wsl_homes()
    paths = {}
    # Hermes
    for h in homes:
        for p in [os.path.join(h, ".hermes", "state.db"),
                  os.path.join(h, ".config", "hermes", "state.db")]:
            if os.path.exists(p):
                paths["hermes_db"] = p
                break
        if "hermes_db" in paths:
            break
    for h in homes:
        for p in [os.path.join(h, ".hermes", "sessions", "sessions.json"),
                  os.path.join(h, ".config", "hermes", "sessions", "sessions.json")]:
            if os.path.exists(p):
                paths["hermes_sessions"] = p
                break
        if "hermes_sessions" in paths:
            break
    # Claude Code
    for h in homes:
        p = os.path.join(h, ".claude")
        if os.path.isdir(os.path.join(p, "projects")):
            paths["claude_dir"] = p
            break
    # CodeX
    for h in homes:
        p = os.path.join(h, ".codex")
        if os.path.isdir(p):
            paths["codex_dir"] = p
            break
    # OpenClaw
    for h in homes:
        p = os.path.join(h, ".openclaw", "agents", "main", "sessions", "sessions.json")
        if os.path.exists(p):
            paths["openclaw_sessions"] = p
            break
    return paths


# ═══════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════

def fmt_num(n: int) -> str:
    if abs(n) < 1000:
        return str(n)
    elif abs(n) < 1_000_000:
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



def fmt_today_lines(per_model: list, fmt_num_fn) -> list:
    """Format per-model today data. Returns [first_line, ...] for printing.
    Uses 📅 今日 prefix for single-model, or header + per-model + 合计 for multi."""
    if not per_model:
        return []
    filtered = [pm for pm in per_model if not _skip_model(pm)]
    if not filtered:
        return []
    models = []
    ti = to = tc = tca = 0
    for pm in filtered:
        m = pm.get("model", "unknown")
        i = pm.get("input", 0) or 0
        o = pm.get("output", 0) or 0
        c = pm.get("cache", 0) or 0
        ca = pm.get("calls", 0) or 0
        models.append((m, i, o, c, ca))
        ti += i
        to += o
        tc += c
        tca += ca

    lines = []
    if len(models) == 1:
        # Single model: compact format with 📅 今日 prefix
        m, i, o, c, ca = models[0]
        t = i + o
        parts = [f"输入 {fmt_num_fn(i)} tokens", f"输出 {fmt_num_fn(o)} tokens",
                 f"总计 {fmt_num_fn(t)} tokens"]
        if c:
            parts.append(f"缓存 {fmt_num_fn(c)} tokens")
        parts.append(f"调用 {ca} 次")
        lines.append(f"  📅 今日 | {' | '.join(parts)}")
    else:
        # Multi model: header + per-model + separator + 合计
        name_w = max((len(m) for m,_,_,_,_ in models), default=4)
        name_w = max(name_w, 4)
        lines.append("  📅 今日")
        for m, i, o, c, ca in models:
            t = i + o
            parts = [f"输入 {fmt_num_fn(i)} tokens", f"输出 {fmt_num_fn(o)} tokens",
                     f"总计 {fmt_num_fn(t)} tokens"]
            if c:
                parts.append(f"缓存 {fmt_num_fn(c)} tokens")
            parts.append(f"调用 {ca} 次")
            lines.append(f"    {m:<{name_w}} | {' | '.join(parts)}")
        sep_len = len(lines[1]) - 4  # minus indent
        lines.append(f"    {'─' * sep_len}")
        tt = ti + to
        parts2 = [f"输入 {fmt_num_fn(ti)} tokens", f"输出 {fmt_num_fn(to)} tokens",
                  f"总计 {fmt_num_fn(tt)} tokens"]
        if tc:
            parts2.append(f"缓存 {fmt_num_fn(tc)} tokens")
        parts2.append(f"调用 {tca} 次")
        lines.append(f"    {'合计':<{name_w}} | {' | '.join(parts2)}")
    return lines
MODEL_CONTEXT_MAP = {
    # ── Anthropic / Claude (all 200K) ──
    "claude-opus-4-7": 200_000,
    "claude-opus-4-5": 200_000,
    "claude-opus-4": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-sonnet-4-5": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-haiku-4-5": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    "claude-haiku-3.5": 200_000,
    "claude-3.5-sonnet": 200_000,
    "claude-3.5-haiku": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,

    # ── OpenAI / GPT ──
    "gpt-4.1": 1_048_576,
    "gpt-4.1-mini": 1_048_576,
    "gpt-4.1-nano": 1_048_576,
    "gpt-4o": 131_072,
    "gpt-4o-mini": 131_072,
    "gpt-4-turbo": 131_072,
    "gpt-4": 131_072,
    "o4-mini": 200_000,
    "o3": 200_000,
    "o3-mini": 200_000,
    "o1": 200_000,
    "o1-pro": 200_000,

    # ── Google / Gemini (all 1M) ──
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.5-flash": 1_048_576,
    "gemini-2.5-flash-lite": 1_048_576,
    "gemini-2.0-flash": 1_048_576,

    # ── DeepSeek ──
    "deepseek-v4-flash": 1_048_576,
    "deepseek-v4-pro": 1_048_576,
    "deepseek-v4": 1_048_576,
    "deepseek-chat": 1_048_576,
    "deepseek-reasoner": 1_048_576,
    "deepseek-r1": 1_048_576,
    "deepseek-v3": 131_072,

    # ── Meta / Llama ──
    "llama-4": 131_072,
    "llama-3.1": 131_072,
    "llama-3": 131_072,

    # ── Mistral ──
    "mistral-large-2": 131_072,
    "mistral-large": 131_072,
    "mistral-small": 131_072,

    # ── 通义千问 / Qwen ──
    "qwen3": 131_072,
    "qwen3-coder": 131_072,
    "qwen2.5-coder": 131_072,
    "qwen-plus": 131_072,
    "qwen-max": 131_072,
    "qwen-turbo": 131_072,

    # ── Kimi / 月之暗面 (Moonshot) ──
    "moonshot-v1-128k": 131_072,
    "moonshot-v1-32k": 32_768,
    "moonshot-v1-8k": 8_192,
    "kimi-latest": 131_072,

    # ── GLM / 智谱 ──
    "glm-4-plus": 131_072,
    "glm-4-long": 1_048_576,
    "glm-4-air": 131_072,
    "glm-4-flash": 131_072,
    "glm-4": 131_072,
    "glm-3-turbo": 131_072,

    # ── Doubao / 字节豆包 ──
    "doubao-pro-128k": 131_072,
    "doubao-pro-32k": 32_768,
    "doubao-lite-32k": 32_768,

    # ── 文心 / 百度 (ERNIE) ──
    "ernie-4.0-turbo": 131_072,
    "ernie-4.0": 8_192,
    "ernie-3.5": 8_192,

    # ── 零一万物 / Yi ──
    "yi-large": 32_768,
    "yi-lightning": 16_384,

    # ── xAI / Grok ──
    "grok-3": 131_072,
    "grok-2": 131_072,
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


def parse_date(s: str) -> tuple:
    """Parse 'YYYY-MM-DD' → (start_ts, end_ts)"""
    dt = datetime.strptime(s.strip(), "%Y-%m-%d")
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = dt.replace(hour=23, minute=59, second=59, microsecond=0)
    return start.timestamp(), end.timestamp()


def parse_time_label(label: str) -> tuple:
    """Parse a time label → (start_ts, end_ts).

    Supports:
      today, yesterday, this-week / week, last-week, last-7d
      YYYY-MM-DD (single day)
      YYYY-MM-DD~YYYY-MM-DD (date range)
    """
    s = label.strip().lower()
    now = datetime.now()

    if s == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), now.timestamp()

    if s == "yesterday":
        d = now - timedelta(days=1)
        start = d.replace(hour=0, minute=0, second=0, microsecond=0)
        end = d.replace(hour=23, minute=59, second=59, microsecond=0)
        return start.timestamp(), end.timestamp()

    if s in ("this-week", "week"):
        monday = now - timedelta(days=now.weekday())
        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), now.timestamp()

    if s == "last-week":
        monday = now - timedelta(days=now.weekday() + 7)
        sunday = monday + timedelta(days=6)
        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = sunday.replace(hour=23, minute=59, second=59, microsecond=0)
        return start.timestamp(), end.timestamp()

    if s == "last-7d":
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), now.timestamp()

    # Date range: YYYY-MM-DD~YYYY-MM-DD
    if "~" in s:
        parts = s.split("~", 1)
        start_ts, _ = parse_date(parts[0])
        _, end_ts = parse_date(parts[1])
        return start_ts, end_ts

    # Single date
    return parse_date(s)


def _display_width(s: str) -> int:
    """计算终端显示宽度（CJK 字符算 2 列，ASCII 算 1 列）。"""
    w = 0
    for c in s:
        code = ord(c)
        if (0x1100 <= code <= 0x115F or    # Hangul Jamo
            0x2E80 <= code <= 0xA4CF or    # CJK Radicals ~ Yi
            0xAC00 <= code <= 0xD7A3 or    # Hangul Syllables
            0xF900 <= code <= 0xFAFF or    # CJK Compatibility Ideographs
            0xFE30 <= code <= 0xFE4F or    # CJK Compatibility Forms
            0xFF01 <= code <= 0xFF60 or    # Fullwidth Forms
            0xFFE0 <= code <= 0xFFE6 or    # Fullwidth Signs
            0x20000 <= code <= 0x2FFFF or  # CJK Extension
            0x30000 <= code <= 0x3FFFF):   # CJK Extension
            w += 2
        else:
            w += 1
    return w


def _pad_to(s: str, width: int, align: str = "<") -> str:
    """按显示宽度填充到指定列宽。"""
    dw = _display_width(s)
    pad = max(0, width - dw)
    if align == ">":
        return " " * pad + s
    else:
        return s + " " * pad


def label_to_display(label: str) -> str:
    """将时间标签转为人类可读的日期字符串，用于对比模式列头。"""
    s = label.strip().lower()
    now = datetime.now()
    if s == "today":
        return now.strftime("%Y-%m-%d")
    if s == "yesterday":
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if s in ("this-week", "week"):
        monday = now - timedelta(days=now.weekday())
        return f"{monday.strftime('%Y-%m-%d')}~{now.strftime('%Y-%m-%d')}"
    if s == "last-week":
        monday = now - timedelta(days=now.weekday() + 7)
        sunday = monday + timedelta(days=6)
        return f"{monday.strftime('%Y-%m-%d')}~{sunday.strftime('%Y-%m-%d')}"
    if s == "last-7d":
        start = now - timedelta(days=7)
        return f"{start.strftime('%Y-%m-%d')}~{now.strftime('%Y-%m-%d')}"
    # 已经是日期或日期段格式，直接返回
    return label


def _skip_model(pm: dict) -> bool:
    """过滤掉 unknown 且无数据的模型条目（输出/导出/监控通用）。"""
    model = (pm.get("model", "") or "").strip()
    if not model or model == "unknown":
        inp = pm.get("input", 0) or 0
        out = pm.get("output", 0) or 0
        cache = pm.get("cache", 0) or 0
        calls = pm.get("calls", 0) or 0
        if inp == 0 and out == 0 and cache == 0 and calls == 0:
            return True
    return False


def format_model_line(model_name: str, inp: int, out: int, cache: int, calls: int,
                      context_window: int = None, session_count: int = None,
                      extra: str = None) -> str:
    """单行模型输出格式。若全为 0 则返回空字符串。"""
    if inp == 0 and out == 0 and cache == 0 and calls == 0:
        return ""

    parts = []
    total = inp + out
    if context_window:
        pct = round(total / context_window * 100, 1) if context_window else 0
        parts.append(f"上下文 {fmt_num(total)}/{fmt_num(context_window)} ({fmt_pct(pct)})")
    if inp > 0 or out > 0 or total > 0:
        if not context_window:
            parts.append(f"总计 {fmt_num(total)}")
        parts.append(f"输入 {fmt_num(inp)}")
        parts.append(f"输出 {fmt_num(out)}")
    if cache > 0:
        parts.append(f"缓存 {fmt_num(cache)}")
    if calls > 0 and session_count != calls:
        parts.append(f"调用 {calls} 次")
    if session_count:
        parts.append(f"{session_count} 轮会话")
    if extra:
        parts.append(extra)
    if not parts:
        parts.append("无数据")
    return f"  {model_name} | {' | '.join(parts)}"


# ═══════════════════════════════════════════════════
#  Agent 基类与数据模型
# ═══════════════════════════════════════════════════

@dataclass
class AgentData:
    """单个 Agent 的统计数据"""
    name: str
    display_name: str
    stats: dict
    raw: str
    per_model: list = None  # [{"model": ..., "input": N, "output": N, "calls": N, "cache": N}, ...]


class BaseAgent(ABC):
    """Agent 检测器基类"""

    # 支持实时上下文占比显示（会话型 Agent 为 True，累计型为 False）
    _has_live_context = False

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
    def collect(self, *, from_ts: float = None, to_ts: float = None) -> AgentData: ...

    def watch(self, interval: int = 5) -> None:
        """实时监控模式"""
        stop_event = threading.Event()

        def _on_signal(sig, frame):
            stop_event.set()

        old_sigint = signal.signal(signal.SIGINT, _on_signal)
        old_sigterm = None
        try:
            old_sigterm = signal.signal(signal.SIGTERM, _on_signal)
        except (ValueError, AttributeError):
            pass  # Windows 上 SIGTERM 不可用

        def _interruptible_sleep(seconds: float) -> bool:
            """中断式睡眠，返回 False 表示被中断"""
            return not stop_event.wait(timeout=seconds)

        watch_start = time.time()
        # 今日起始时间戳，用于 📅 今日合计查询
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        print(f"\n📡 实时监控 [{self.display_name()}] — 每 {interval} 秒刷新 (Ctrl+C 停止)\n")

        # ── 首次基线 ──
        try:
            data_first = self.collect()
        except Exception as e:
            print(f"  ⚠️ 无法读取数据: {e}")
            print("👋 监控已停止")
            return
        bl_models = {}
        if data_first.per_model:
            for pm in data_first.per_model:
                bl_models[pm["model"]] = {
                    "input": pm.get("input", 0),
                    "output": pm.get("output", 0),
                    "calls": pm.get("calls", 0),
                    "cache": pm.get("cache", 0),
                }
        else:
            m = data_first.stats.get("model", "")
            if m and m != "?" and data_first.stats.get("input_tokens", 0) > 0:
                bl_models[m] = {
                    "input": data_first.stats.get("input_tokens", 0),
                    "output": data_first.stats.get("output_tokens", 0),
                    "calls": data_first.stats.get("api_calls", 0),
                    "cache": data_first.stats.get("cache_read", 0),
                }

        # ── 初始状态 ──
        bl_initial = {k: dict(v) for k, v in bl_models.items()}  # 保存初始基线，用于最终汇总
        print("初始状态:")
        has_data = False
        for mn, mv in bl_models.items():
            total = mv["input"] + mv["output"]
            parts = []
            if self._has_live_context:
                cw = detect_context(mn)
                pct = round(total / cw * 100, 1) if cw else 0
                parts.append(f"上下文 {fmt_num(total)}/{fmt_num(cw)} ({fmt_pct(pct)})")
            else:
                parts.append(f"总计 {fmt_num(total)}")
            parts.extend([
                f"输入 {fmt_num(mv['input'])} tokens",
                f"输出 {fmt_num(mv['output'])} tokens"
            ])
            if mv.get("cache", 0):
                parts.append(f"缓存 {fmt_num(mv['cache'])} tokens")
            parts.append(f"调用 {mv['calls']}")
            print(f"  {mn} | {' | '.join(parts)}")
            has_data = True
        if not has_data:
            print("  (暂无数据，等待会话开始...)")
        print()

        # ── 监控循环 ──
        while not stop_event.is_set():
            if not _interruptible_sleep(interval):
                break
            if stop_event.is_set():
                break
            tick_start = time.monotonic()
            try:
                data = self.collect()
            except Exception as e:
                print(f"  ⚠️ {e}")
                continue

            now_models = {}
            if data.per_model:
                for pm in data.per_model:
                    now_models[pm["model"]] = {
                        "input": pm.get("input", 0),
                        "output": pm.get("output", 0),
                        "calls": pm.get("calls", 0),
                        "cache": pm.get("cache", 0),
                    }
            else:
                m = data.stats.get("model", "?")
                now_models[m] = {
                    "input": data.stats.get("input_tokens", 0),
                    "output": data.stats.get("output_tokens", 0),
                    "calls": data.stats.get("api_calls", 0),
                    "cache": data.stats.get("cache_read", 0),
                }

            # 对比上一次状态，列出增量
            changed_models = []
            total_delta_tok = 0
            total_delta_calls = 0
            for mn, mv in now_models.items():
                bl = bl_models.get(mn, {"input": 0, "output": 0, "calls": 0, "cache": 0})
                d_in = mv["input"] - bl["input"]
                d_out = mv["output"] - bl["output"]
                d_calls = mv["calls"] - bl["calls"]
                d_cache = mv["cache"] - bl["cache"]
                d_tok = d_in + d_out
                if d_tok > 0 or d_calls > 0 or d_cache > 0:
                    changed_models.append((mn, d_in, d_out, d_tok, d_calls, d_cache))
                    total_delta_tok += d_tok
                    total_delta_calls += d_calls
                elif d_tok < 0 or d_calls < 0:
                    bl_models[mn] = mv

            # 每个 tick 合并显示：增量/累计（一行完成）
            ts = datetime.now().strftime("%H:%M:%S")
            any_delta = bool(changed_models)
            if any_delta:
                summary_parts = []
                if total_delta_tok > 0:
                    summary_parts.append(f"+{fmt_num(total_delta_tok)} tokens")
                elif total_delta_tok < 0:
                    summary_parts.append(f"{fmt_num(total_delta_tok)} tokens")
                if total_delta_calls > 0:
                    summary_parts.append(f"+{total_delta_calls} 调用")
                elif total_delta_calls < 0:
                    summary_parts.append(f"{total_delta_calls} 调用")
                print(f"── [{ts}] {' '.join(summary_parts)} ──")
            else:
                print(f"── [{ts}] 无变化 ──")

            if any_delta:
                for mn, mv in now_models.items():
                    bl = bl_models.get(mn, {"input": 0, "output": 0, "calls": 0, "cache": 0})
                    d_in = mv["input"] - bl["input"]
                    d_out = mv["output"] - bl["output"]
                    d_tok = d_in + d_out
                    d_cache = mv.get("cache", 0) - bl.get("cache", 0)
                    d_calls = mv["calls"] - bl["calls"]
                    has_delta = d_tok > 0 or d_cache > 0 or d_calls > 0

                    total = mv["input"] + mv["output"]
                    parts = []
                    if self._has_live_context:
                        cw = detect_context(mn)
                        pct = round(total / cw * 100, 1) if cw else 0
                        parts.append(f"上下文 {fmt_num(total)}/{fmt_num(cw)} ({fmt_pct(pct)})")
                    else:
                        parts.append(f"总计 {fmt_num(total)}")

                    if has_delta:
                        parts.append(f"输入 +{fmt_num(d_in)}/{fmt_num(mv['input'])} tokens")
                        parts.append(f"输出 +{fmt_num(d_out)}/{fmt_num(mv['output'])} tokens")
                        if d_cache or mv.get("cache", 0):
                            parts.append(f"缓存 +{fmt_num(d_cache)}/{fmt_num(mv.get('cache', 0))} tokens")
                        parts.append(f"调用 +{d_calls}/{mv['calls']}")
                    else:
                        parts.append(f"输入 {fmt_num(mv['input'])} tokens")
                        parts.append(f"输出 {fmt_num(mv['output'])} tokens")
                        if mv.get("cache", 0):
                            parts.append(f"缓存 {fmt_num(mv['cache'])} tokens")
                        parts.append(f"调用 {mv['calls']}")

                    print(f"  {mn} | {' | '.join(parts)}")

                    # 更新基线
                    if has_delta:
                        bl_models[mn] = mv

            # 📅 今日合计（每次有变化时刷新）
            if any_delta:
                try:
                    today_data = self.collect(from_ts=today_start)
                    today_lines = fmt_today_lines(today_data.per_model or (
                        [{
                            "model": today_data.stats.get("model", "?"),
                            "input": today_data.stats.get("input_tokens", 0),
                            "output": today_data.stats.get("output_tokens", 0),
                            "cache": today_data.stats.get("cache_read", 0),
                            "calls": today_data.stats.get("api_calls", 0),
                        }] if today_data.stats else []), fmt_num)
                    for line in today_lines:
                        print(line)
                except Exception:
                    pass

            # 精确间隔补偿
            elapsed = time.monotonic() - tick_start
            if elapsed < interval and not stop_event.is_set():
                _interruptible_sleep(interval - elapsed)

        # ── 停止汇总：基于最新累计值 ──
        print()
        print("━" * 60)
        print("  📊 本次监控汇总")
        print("━" * 60)

        # 最终累计状态
        if bl_models:
            print("  最终状态:")
            for mn, mv in sorted(bl_models.items()):
                total = mv["input"] + mv["output"]
                parts = []
                if self._has_live_context:
                    cw = detect_context(mn)
                    pct = round(total / cw * 100, 1) if cw else 0
                    parts.append(f"上下文 {fmt_num(total)}/{fmt_num(cw)} ({fmt_pct(pct)})")
                else:
                    parts.append(f"总计 {fmt_num(total)}")
                parts.extend([f"输入 {fmt_num(mv['input'])} tokens",
                              f"输出 {fmt_num(mv['output'])} tokens"])
                if mv.get("cache", 0):
                    parts.append(f"缓存 {fmt_num(mv['cache'])} tokens")
                parts.append(f"调用 {mv['calls']}")
                print(f"  {mn} | {' | '.join(parts)}")

            # 📅 今日累计
            try:
                today_data = self.collect(from_ts=today_start)
                today_lines = fmt_today_lines(today_data.per_model or (
                    [{
                        "model": today_data.stats.get("model", "?"),
                        "input": today_data.stats.get("input_tokens", 0),
                        "output": today_data.stats.get("output_tokens", 0),
                        "cache": today_data.stats.get("cache_read", 0),
                        "calls": today_data.stats.get("api_calls", 0),
                    }] if today_data.stats else []), fmt_num)
                if today_lines:
                    print(f"  📅 今日累计:")
                    for line in today_lines:
                        print(line)
            except Exception:
                pass

            # 总增量（最新累计 - 初始基线）
            total_d_tok = total_d_cache = total_d_calls = 0
            total_d_in = total_d_out = 0
            delta_lines = []
            for mn, mv in sorted(bl_models.items()):
                init = bl_initial.get(mn, {"input": 0, "output": 0, "cache": 0, "calls": 0})
                d_in = mv["input"] - init["input"]
                d_out = mv["output"] - init["output"]
                d_tok = d_in + d_out
                d_cache = mv.get("cache", 0) - init.get("cache", 0)
                d_calls = mv["calls"] - init["calls"]
                total_d_in += d_in; total_d_out += d_out
                total_d_tok += d_tok; total_d_cache += d_cache; total_d_calls += d_calls
                if d_tok > 0 or d_cache > 0 or d_calls > 0:
                    parts = [f"总计 +{fmt_num(d_tok)}",
                             f"输入 +{fmt_num(d_in)}",
                             f"输出 +{fmt_num(d_out)}"]
                    if d_cache:
                        parts.append(f"缓存 +{fmt_num(d_cache)}")
                    parts.append(f"+{d_calls} 调用")
                    delta_lines.append(f"  {mn} | {' | '.join(parts)}")

            if delta_lines:
                print(f"\n  监控期间增量:")
                for dl in delta_lines:
                    print(dl)
                if len(delta_lines) > 1:
                    print(f"  {'─' * 50}")
                    sum_parts = [f"总计 +{fmt_num(total_d_tok)}",
                                 f"输入 +{fmt_num(total_d_in)}",
                                 f"输出 +{fmt_num(total_d_out)}"]
                    if total_d_cache:
                        sum_parts.append(f"缓存 +{fmt_num(total_d_cache)}")
                    sum_parts.append(f"+{total_d_calls} 调用")
                    print(f"  合计 | {' | '.join(sum_parts)}")
        else:
            print("  监控期间无数据")
        print("👋 监控已停止")


# ═══════════════════════════════════════════════════
#  Hermes
# ═══════════════════════════════════════════════════

def _find_hermes_db() -> str:
    """获取 Hermes 数据库路径，优先从配置读取"""
    cfg = _load_agent_paths()
    if "hermes_db" in cfg:
        return cfg["hermes_db"]
    return _resolve_path(".hermes/state.db")


def _find_hermes_sessions() -> str:
    """获取 Hermes sessions 文件路径，优先从配置读取"""
    cfg = _load_agent_paths()
    if "hermes_sessions" in cfg:
        return cfg["hermes_sessions"]
    return _resolve_path(".hermes/sessions/sessions.json")


def _hermes_current_session_id() -> str | None:
    """从 sessions.json 读取当前活跃会话 ID。"""
    sessions_path = _find_hermes_sessions()
    try:
        with open(sessions_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        for key, val in data.items():
            if isinstance(val, dict) and val.get("session_id"):
                return val["session_id"]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


class HermesAgent(BaseAgent):
    _has_live_context = True  # 有当前会话概念，上下文占比有意义

    @staticmethod
    def name() -> str:
        return "hermes"

    @staticmethod
    def display_name() -> str:
        return "Hermes"

    @staticmethod
    def detect() -> bool:
        db = _find_hermes_db()
        if os.path.exists(db):
            return True
        # WSL 路径可能 UNC 不通但 wsl.exe 已验证存在（_resolve_path 已处理）
        return db != os.path.join(os.path.expanduser("~"), ".hermes", "state.db")

    def _try_wsl_fallback(self, hermes_db, error_msg, from_ts=None, to_ts=None):
        """WSL 路径 DB 不可用时，通过 wsl.exe 在 WSL 内读取。"""
        distro, _ = _wsl_unc_to_linux(hermes_db)
        if not distro:
            return None
        if "locked" not in error_msg.lower() and "unable to open" not in error_msg.lower():
            return None
        result = _hermes_collect_via_wsl(hermes_db, from_ts, to_ts)
        if not result:
            return None
        if not result.get("rows"):
            # WSL 查询成功但该时段无数据，返回空 AgentData
            label = "Hermes (WSL)"
            return AgentData(name="hermes", display_name=label,
                             stats={}, raw=f"{label}: 该时间段内无会话记录", per_model=[])
        rows = result["rows"]
        per_model_list = []
        raw_lines = ["📊 Hermes (WSL)"]
        ti = to = tc = tca = tsess = 0
        for r in rows:
            m = r.get("model") or "unknown"
            inp = int(r.get("inp") or 0)
            out = int(r.get("out") or 0)
            cache = int(r.get("cache") or 0)
            calls = int(r.get("calls") or 0)
            cnt = int(r.get("cnt") or 0)
            ti += inp; to += out; tc += cache; tca += calls; tsess += cnt
            per_model_list.append({"model": m, "input": inp, "output": out, "calls": calls, "cache": cache})
            line = format_model_line(m, inp, out, cache, calls, session_count=cnt)
            if line:
                raw_lines.append(line)
        raw = "\n".join(raw_lines)
        stats = {
            "model": ", ".join(sorted({(r.get("model") or "unknown") for r in rows})),
            "input_tokens": ti, "output_tokens": to, "cache_read": tc,
            "api_calls": tca, "total_tokens": ti + to, "session_count": tsess,
        }
        return AgentData(name="hermes", display_name="Hermes", stats=stats, raw=raw, per_model=per_model_list)

    def collect(self, *, from_ts: float = None, to_ts: float = None) -> AgentData:
        hermes_db = _find_hermes_db()
        try:
            return self._collect_impl(hermes_db, from_ts, to_ts)
        except Exception as e:
            fb = self._try_wsl_fallback(hermes_db, str(e), from_ts, to_ts)
            if fb:
                return fb
            raise

    def _collect_impl(self, hermes_db, from_ts, to_ts):
        conn = sqlite3.connect(hermes_db)
        conn.row_factory = sqlite3.Row

        # ── schema 兼容：检测旧版 Hermes 缺少的列 ──
        has_api_calls = True
        has_tool_calls = True
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
            if "api_call_count" not in cols:
                has_api_calls = False
            if "tool_call_count" not in cols:
                has_tool_calls = False
        except Exception:
            pass

        if from_ts is not None or to_ts is not None:
            # ── 时间段统计 ──
            where = []
            params = []
            if from_ts is not None:
                # ended_at IS NULL 仅对 1 天内的会话放行，避免旧会话 ended_at 残留 NULL
                grace = from_ts - 86400
                where.append("(started_at >= ? OR (ended_at IS NULL AND started_at >= ?) OR (ended_at IS NOT NULL AND ended_at >= ?))")
                params.append(from_ts)
                params.append(grace)
                params.append(from_ts)
            if to_ts is not None:
                where.append("started_at <= ?")
                params.append(to_ts)
            clause = " AND ".join(where)

            calls_expr = "SUM(api_call_count)" if has_api_calls else "0"
            tools_expr = "SUM(tool_call_count)" if has_tool_calls else "0"
            cur = conn.execute(
                f"SELECT model, SUM(input_tokens) as inp, SUM(output_tokens) as out, "
                f"SUM(cache_read_tokens) as cache, {calls_expr} as calls, "
                f"{tools_expr} as tools, COUNT(*) as cnt "
                f"FROM sessions WHERE {clause} GROUP BY model",
                params
            )
            rows = cur.fetchall()
            conn.close()

            if not rows:
                return AgentData(
                    name="hermes", display_name="Hermes",
                    stats={}, raw="Hermes: 该时间段内无会话记录"
                )

            total_inp = sum(r["inp"] or 0 for r in rows)
            total_out = sum(r["out"] or 0 for r in rows)
            total_cache = sum(r["cache"] or 0 for r in rows)
            total_calls = sum(r["calls"] or 0 for r in rows)
            total_sessions = sum(r["cnt"] or 0 for r in rows)

            per_model_list = []
            raw_lines = ["📊 Hermes"]
            for r in rows:
                m = r["model"] or "unknown"
                inp = r["inp"] or 0
                out = r["out"] or 0
                cache = r["cache"] or 0
                calls = r["calls"] or 0
                cnt = r["cnt"] or 0
                per_model_list.append({"model": m, "input": inp, "output": out,
                                        "calls": calls, "cache": cache})
                line = format_model_line(m, inp, out, cache, calls, session_count=cnt)
                if line:
                    raw_lines.append(line)

            raw = "\n".join(raw_lines)

            stats = {
                "model": ", ".join(sorted({r["model"] or "unknown" for r in rows})),
                "input_tokens": total_inp,
                "output_tokens": total_out,
                "cache_read": total_cache,
                "api_calls": total_calls,
                "total_tokens": total_inp + total_out,
                "session_count": total_sessions,
            }

            return AgentData(name="hermes", display_name="Hermes",
                             stats=stats, raw=raw, per_model=per_model_list)

        # ── 当前会话 ──
        # 优先从 sessions.json 获取当前活跃会话 ID，精确查询
        calls_col = "api_call_count" if has_api_calls else "0 as api_call_count"
        tools_col = "tool_call_count" if has_tool_calls else "0 as tool_call_count"
        current_id = _hermes_current_session_id()
        if current_id:
            cur = conn.execute(
                f"SELECT id, model, input_tokens, output_tokens, cache_read_tokens, "
                f"{calls_col}, {tools_col}, title "
                f"FROM sessions WHERE id = ?",
                (current_id,)
            )
        else:
            cur = conn.execute(
                f"SELECT id, model, input_tokens, output_tokens, cache_read_tokens, "
                f"{calls_col}, {tools_col}, title "
                f"FROM sessions ORDER BY started_at DESC LIMIT 1"
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

        cur2 = conn.execute("SELECT COUNT(*) as cnt FROM sessions")
        session_count = cur2.fetchone()["cnt"]
        conn.close()

        cw = detect_context(model)

        per_model_list = [{"model": model, "input": inp, "output": out,
                           "calls": calls, "cache": cache}]
        line = format_model_line(model, inp, out, cache, calls,
                                 context_window=cw,
                                 extra=f"第 {session_count} 轮 \"{title}\"")
        raw = "📊 Hermes" + ("\n" + line if line else "")

        stats = {
            "model": model,
            "input_tokens": inp,
            "output_tokens": out,
            "cache_read": cache,
            "api_calls": calls,
            "tool_calls": tools,
            "context_window": cw,
            "context_pct": round((inp + out) / cw * 100, 1) if cw else 0,
            "total_tokens": inp + out,
            "session_count": session_count,
            "title": title,
        }

        return AgentData(name="hermes", display_name="Hermes",
                         stats=stats, raw=raw, per_model=per_model_list)


# ═══════════════════════════════════════════════════
#  Claude Code
# ═══════════════════════════════════════════════════

def _find_claude_dir() -> str:
    """获取 Claude Code 目录，优先从配置读取"""
    cfg = _load_agent_paths()
    if "claude_dir" in cfg:
        return cfg["claude_dir"]
    return _resolve_path(".claude")


class ClaudeCodeAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "claude-code"

    @staticmethod
    def display_name() -> str:
        return "Claude Code"

    @staticmethod
    def detect() -> bool:
        cd = _find_claude_dir()
        if os.path.isdir(os.path.join(cd, "projects")):
            return True
        native = os.path.join(os.path.expanduser("~"), ".claude")
        return cd != native

    @staticmethod
    def _ts_in_range(ts_str: str, from_ts: float = None, to_ts: float = None) -> bool:
        """Check if an ISO timestamp string falls within the given Unix time range."""
        if from_ts is None and to_ts is None:
            return True
        try:
            # Parse ISO 8601 timestamp (e.g. '2026-05-14T18:07:28.252Z')
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            msg_ts = dt.timestamp()
            if from_ts is not None and msg_ts < from_ts:
                return False
            if to_ts is not None and msg_ts > to_ts:
                return False
            return True
        except (ValueError, TypeError):
            return True  # can't parse → include to be safe

    def _find_sessions(self, from_ts: float = None, to_ts: float = None):
        projects_dir = os.path.join(_find_claude_dir(), "projects")
        if not os.path.isdir(projects_dir):
            return []
        sessions = []
        for proj in os.listdir(projects_dir):
            proj_dir = os.path.join(projects_dir, proj)
            if not os.path.isdir(proj_dir):
                continue
            for root, _dirs, files in os.walk(proj_dir):
                for fname in files:
                    if fname.endswith(".jsonl") and not fname.endswith(".trajectory.jsonl"):
                        fpath = os.path.join(root, fname)
                        sessions.append((proj, fname, fpath))
        return sorted(sessions, key=lambda x: os.path.getmtime(x[2]), reverse=True)

    def collect(self, *, from_ts: float = None, to_ts: float = None) -> AgentData:
        sessions = self._find_sessions()
        if not sessions:
            return AgentData(
                name="claude-code", display_name="Claude Code",
                stats={}, raw="Claude Code: 尚无会话记录"
            )

        per_model_data = {}
        total_sub = 0
        project_names = set()

        for proj, fname, fpath in sessions:
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
                            if not self._ts_in_range(msg.get("timestamp", ""), from_ts, to_ts):
                                continue
                            model = msg.get("message", {}).get("model") or msg.get("model", "unknown")
                            if model.startswith("<"):
                                model = "subagent"
                            if model not in per_model_data:
                                per_model_data[model] = {"input": 0, "output": 0, "calls": 0, "cache": 0}
                            usage = msg.get("message", {}).get("usage") or msg.get("usage", {})
                            per_model_data[model]["input"] += usage.get("input_tokens", 0)
                            per_model_data[model]["output"] += usage.get("output_tokens", 0)
                            per_model_data[model]["cache"] += usage.get("cache_read_input_tokens", 0)
                            per_model_data[model]["calls"] += 1
                        if msg.get("toolUseResult") and "usage" in msg["toolUseResult"]:
                            total_sub += 1
            except Exception:
                continue

        if not per_model_data:
            return AgentData(
                name="claude-code", display_name="Claude Code",
                stats={}, raw="Claude Code: 会话文件中未解析到有效数据"
            )

        total_calls = sum(d["calls"] for d in per_model_data.values())
        total_input = sum(d["input"] for d in per_model_data.values())
        total_output = sum(d["output"] for d in per_model_data.values())
        total_cache = sum(d["cache"] for d in per_model_data.values())
        models_sorted = sorted(per_model_data.keys())

        # 过滤掉无效模型（input+output=0，无实际数据）
        meaningful_models = [
            mn for mn in models_sorted
            if per_model_data[mn]["input"] + per_model_data[mn]["output"] > 0
        ]

        per_model_list = []
        for mn in meaningful_models:
            md = per_model_data[mn]
            per_model_list.append({
                "model": mn,
                "input": md["input"],
                "output": md["output"],
                "calls": md["calls"],
                "cache": md["cache"],
            })

        raw_lines = ["📊 Claude Code"]
        for mn in meaningful_models:
            md = per_model_data[mn]
            line = format_model_line(
                mn, md["input"], md["output"], md["cache"], md["calls"],
            )
            if line:
                raw_lines.append(line)
        raw_lines.append(f"  ────────────────────────────────────")
        raw_lines.append(f"  子代理: {total_sub} 次 | 会话: {len(sessions)} 个 | 项目: {len(project_names)} 个")
        raw = "\n".join(raw_lines)

        stats = {
            "model": ", ".join(models_sorted),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cache_read": total_cache,
            "api_calls": total_calls,
            "sub_calls": total_sub,
            "total_tokens": total_input + total_output,
            "session_count": len(sessions),
            "projects": len(project_names),
        }

        return AgentData(name="claude-code", display_name="Claude Code",
                         stats=stats, raw=raw, per_model=per_model_list)


# ═══════════════════════════════════════════════════
#  CodeX
# ═══════════════════════════════════════════════════

def _find_codex_db() -> Optional[str]:
    """获取 CodeX 数据库路径，优先从配置读取"""
    cfg = _load_agent_paths()
    if "codex_dir" in cfg:
        codex_dir = cfg["codex_dir"]
        if os.path.isdir(codex_dir):
            dbs = sorted(
                [f for f in os.listdir(codex_dir) if re.match(r'^state_\d+\.sqlite$', f)],
                reverse=True
            )
            return os.path.join(codex_dir, dbs[0]) if dbs else None
    # 回退到标准路径（含 WSL）
    codex_dir = _resolve_path(".codex")
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
        db = _find_codex_db()
        if db is not None:
            if os.path.isdir(db) or os.path.exists(db):
                return True
            native = os.path.join(os.path.expanduser("~"), ".codex")
            return db != native
        return False

    def collect(self, *, from_ts: float = None, to_ts: float = None) -> AgentData:
        db = _find_codex_db()
        if not db:
            return AgentData(
                name="codex", display_name="CodeX",
                stats={}, raw="CodeX: 未检测到数据库文件"
            )
        try:
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row

            if from_ts is not None or to_ts is not None:
                where = []
                params = []
                if from_ts is not None:
                    where.append("created_at >= ?")
                    params.append(int(from_ts))
                if to_ts is not None:
                    where.append("created_at <= ?")
                    params.append(int(to_ts))
                clause = " AND ".join(where)

                cur = conn.execute(
                    f"SELECT model, model_provider, SUM(tokens_used) as tokens, COUNT(*) as cnt "
                    f"FROM threads WHERE {clause} GROUP BY model, model_provider",
                    params
                )
                rows = cur.fetchall()
                conn.close()

                if not rows:
                    return AgentData(
                        name="codex", display_name="CodeX",
                        stats={}, raw="CodeX: 该时间段内无会话记录"
                    )

                per_model_list = []
                raw_lines = ["📊 CodeX"]
                total_tok = 0
                total_cnt = 0
                for r in rows:
                    model = r["model"] or r["model_provider"] or "codex-default"
                    ts = r["tokens"] or 0
                    cnt = r["cnt"] or 0
                    per_model_list.append({"model": model, "input": ts, "output": 0,
                                            "calls": cnt, "cache": 0})
                    # CodeX 不区分输入/输出，仅显示总计；thread=session，调用数=会话数
                    if ts > 0 or cnt > 0:
                        parts = [f"总计 {fmt_num(ts)}"] if ts > 0 else []
                        parts.append(f"{cnt} 轮会话")
                        raw_lines.append(f"  {model} | {' | '.join(parts)}")
                    total_tok += ts
                    total_cnt += cnt

                raw = "\n".join(raw_lines)
                stats = {
                    "model": ", ".join(sorted({r["model"] or "unknown" for r in rows if r["model"]})),
                    "total_tokens": total_tok,
                    "session_count": total_cnt,
                }
                return AgentData(name="codex", display_name="CodeX",
                                 stats=stats, raw=raw, per_model=per_model_list)

            # ── 默认：汇总所有线程（按模型） ──
            cur = conn.execute(
                "SELECT model, model_provider, SUM(tokens_used) as tokens, COUNT(*) as cnt "
                "FROM threads GROUP BY model, model_provider"
            )
            rows = cur.fetchall()

            cur2 = conn.execute("SELECT COUNT(*) as cnt FROM threads")
            total_sessions = cur2.fetchone()["cnt"] or 0
            conn.close()

            if not rows:
                return AgentData(
                    name="codex", display_name="CodeX",
                    stats={}, raw="CodeX: 尚无会话记录"
                )

            per_model_list = []
            raw_lines = ["📊 CodeX"]
            total_tok = 0
            total_cnt = 0
            model_count = 0
            for r in rows:
                model = r["model"] or r["model_provider"] or "codex-default"
                ts = r["tokens"] or 0
                cnt = r["cnt"] or 0
                per_model_list.append({"model": model, "input": ts, "output": 0,
                                        "calls": cnt, "cache": 0})
                # CodeX 不区分输入/输出，仅显示总计；thread=session
                if ts > 0 or cnt > 0:
                    parts = [f"总计 {fmt_num(ts)}"] if ts > 0 else []
                    parts.append(f"{cnt} 轮会话")
                    raw_lines.append(f"  {model} | {' | '.join(parts)}")
                    model_count += 1
                total_tok += ts
                total_cnt += cnt

            # ── 合计（多模型时显示） ──
            if model_count > 1:
                raw_lines.append(f"  {'─' * 36}")
                raw_lines.append(f"  合计 | 总计 {fmt_num(total_tok)} | {total_cnt} 轮会话")

            if len(rows) == 1 and total_sessions > rows[0]["cnt"]:
                raw_lines[-1] = raw_lines[-1].rstrip() + f" | 共 {total_sessions} 次会话"

            raw = "\n".join(raw_lines)
            stats = {
                "model": ", ".join(sorted({r["model"] or "unknown" for r in rows if r["model"]})),
                "total_tokens": total_tok,
                "session_count": total_sessions,
            }
            return AgentData(name="codex", display_name="CodeX",
                             stats=stats, raw=raw, per_model=per_model_list)

        except Exception as e:
            return AgentData(
                name="codex", display_name="CodeX",
                stats={}, raw=f"CodeX: 读取失败 — {e}"
            )


# ═══════════════════════════════════════════════════
#  OpenClaw
# ═══════════════════════════════════════════════════

def _find_openclaw_sessions_dir() -> Optional[str]:
    """获取 OpenClaw 会话目录（含 .jsonl 文件），优先从配置读取"""
    cfg = _load_agent_paths()
    if "openclaw_sessions" in cfg:
        p = cfg["openclaw_sessions"]
        # 可能是 sessions.json 路径（取父目录）或目录路径
        if p.endswith(".json"):
            d = os.path.dirname(p)
            if os.path.isdir(d):
                return d
        elif os.path.isdir(p):
            return p
    candidates = [
        _resolve_path(".openclaw/agents/main/sessions"),
    ]
    for d in candidates:
        if os.path.isdir(d):
            return d
    return None


def _find_openclaw_sessions() -> Optional[str]:
    """检测 OpenClaw 会话索引文件（sessions.json），用于 detect()"""
    cfg = _load_agent_paths()
    if "openclaw_sessions" in cfg:
        p = cfg["openclaw_sessions"]
        if os.path.exists(p):
            return p
    candidates = [
        _resolve_path(".openclaw/agents/main/sessions/sessions.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _openclaw_parse_jsonl(fpath: str, from_ts: float = None, to_ts: float = None) -> dict:
    """解析单个 OpenClaw .jsonl 文件，返回 {model: {input, output, cache, calls}}"""
    per_model = {}
    current_model = "unknown"
    current_provider = ""
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
                t = msg.get("type", "")

                # 跟踪模型切换
                if t == "model_change":
                    p = msg.get("provider", "")
                    m = msg.get("modelId", "")
                    if m:
                        current_model = f"{m} ({p})" if p else m
                        current_provider = p
                    continue

                # 仅处理 assistant 消息
                if t != "message":
                    continue
                mrole = msg.get("message", {}).get("role", "")
                if mrole != "assistant":
                    continue

                # 时间过滤
                ts_str = msg.get("timestamp", "")
                if ts_str and (from_ts is not None or to_ts is not None):
                    try:
                        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        msg_ts = dt.timestamp()
                        if from_ts is not None and msg_ts < from_ts:
                            continue
                        if to_ts is not None and msg_ts > to_ts:
                            continue
                    except (ValueError, TypeError):
                        pass

                usage = msg.get("message", {}).get("usage", {})
                inp = usage.get("input", 0) or 0
                out = usage.get("output", 0) or 0
                cache = usage.get("cacheRead", 0) or 0

                # 获取本次消息的模型名（优先级：msg.model > current_model）
                model = msg.get("message", {}).get("model", "") or current_model
                if model not in per_model:
                    per_model[model] = {"input": 0, "output": 0, "calls": 0, "cache": 0}
                per_model[model]["input"] += inp
                per_model[model]["output"] += out
                per_model[model]["cache"] += cache
                per_model[model]["calls"] += 1
    except Exception:
        return {}
    return per_model


class OpenClawAgent(BaseAgent):
    _has_live_context = True  # 有当前会话概念，上下文占比有意义

    @staticmethod
    def name() -> str:
        return "openclaw"

    @staticmethod
    def display_name() -> str:
        return "OpenClaw"

    @staticmethod
    def detect() -> bool:
        sd = _find_openclaw_sessions_dir()
        sf = _find_openclaw_sessions()
        if sd is not None and os.path.isdir(sd):
            return True
        if sf is not None and os.path.exists(sf):
            return True
        native = os.path.join(os.path.expanduser("~"), ".openclaw")
        if sd and sd != os.path.join(native, "agents", "main", "sessions"):
            return True
        if sf and sf != os.path.join(native, "agents", "main", "sessions", "sessions.json"):
            return True
        return False

    def collect(self, *, from_ts: float = None, to_ts: float = None) -> AgentData:
        # ── 模式 A：优先从 .jsonl 文件解析（含真实 usage 数据） ──
        sess_dir = _find_openclaw_sessions_dir()
        if sess_dir is not None:
            try:
                jsonl_files = sorted(
                    [f for f in os.listdir(sess_dir)
                     if f.endswith(".jsonl") and not f.endswith(".trajectory.jsonl")]
                )
            except OSError:
                jsonl_files = []
            if jsonl_files:
                per_model_data = {}
                for fname in jsonl_files:
                    fpath = os.path.join(sess_dir, fname)
                    pm = _openclaw_parse_jsonl(fpath, from_ts, to_ts)
                    for model, d in pm.items():
                        if model not in per_model_data:
                            per_model_data[model] = {"input": 0, "output": 0, "calls": 0, "cache": 0}
                        per_model_data[model]["input"] += d["input"]
                        per_model_data[model]["output"] += d["output"]
                        per_model_data[model]["calls"] += d["calls"]
                        per_model_data[model]["cache"] += d["cache"]

                if not per_model_data:
                    return AgentData(
                        name="openclaw", display_name="OpenClaw",
                        stats={}, raw="OpenClaw: 尚无会话" if from_ts is None else "OpenClaw: 该时间段内无会话"
                    )

                total_input = sum(d["input"] for d in per_model_data.values())
                total_output = sum(d["output"] for d in per_model_data.values())
                total_cache = sum(d["cache"] for d in per_model_data.values())
                total_calls = sum(d["calls"] for d in per_model_data.values())

                models_sorted = sorted(per_model_data.keys())
                per_model_list = []
                raw_lines = ["📊 OpenClaw"]
                for mn in models_sorted:
                    md = per_model_data[mn]
                    per_model_list.append({
                        "model": mn, "input": md["input"], "output": md["output"],
                        "calls": md["calls"], "cache": md["cache"],
                    })
                    cw = detect_context(mn)
                    if from_ts is not None or to_ts is not None:
                        line = format_model_line(mn, md["input"], md["output"], md["cache"],
                                                  md["calls"], session_count=md["calls"])
                    else:
                        line = format_model_line(mn, md["input"], md["output"], md["cache"],
                                                  md["calls"], context_window=cw)
                    if line:
                        raw_lines.append(line)

                raw = "\n".join(raw_lines)
                model_list = ", ".join(models_sorted)
                stats = {
                    "model": model_list,
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                    "cache_read": total_cache,
                    "api_calls": total_calls,
                    "total_tokens": total_input + total_output,
                    "session_count": len(jsonl_files),
                }
                if from_ts is None and to_ts is None:
                    first_model = models_sorted[0] if models_sorted else "unknown"
                    cw = detect_context(first_model)
                    stats["context_window"] = cw
                    stats["context_pct"] = round((total_input + total_output) / cw * 100, 1) if cw else 0

                return AgentData(name="openclaw", display_name="OpenClaw",
                                 stats=stats, raw=raw, per_model=per_model_list)
            # 有目录但无 .jsonl → 降级读 sessions.json

        # ── 模式 B：从 sessions.json 读取（回退方案） ──
        oc_path = _find_openclaw_sessions()
        if oc_path is None:
            return AgentData(
                name="openclaw", display_name="OpenClaw",
                stats={}, raw="OpenClaw: 数据文件不存在"
            )
        try:
            with open(oc_path, encoding="utf-8") as f:
                data = json.load(f)

            agents = []
            if isinstance(data, dict):
                for agent_key, session in data.items():
                    if isinstance(session, dict):
                        if from_ts is not None or to_ts is not None:
                            ts = session.get("startedAt", 0) or session.get("updatedAt", 0)
                            if from_ts is not None and ts < from_ts:
                                continue
                            if to_ts is not None and ts > to_ts:
                                continue
                        agents.append(session)
            elif isinstance(data, list):
                for session in data:
                    if isinstance(session, dict):
                        if from_ts is not None or to_ts is not None:
                            ts = session.get("startedAt", 0) or session.get("updatedAt", 0)
                            if from_ts is not None and ts < from_ts:
                                continue
                            if to_ts is not None and ts > to_ts:
                                continue
                        agents.append(session)

            if not agents:
                return AgentData(
                    name="openclaw", display_name="OpenClaw",
                    stats={}, raw="OpenClaw: 尚无会话" if from_ts is None else "OpenClaw: 该时间段内无会话"
                )

            # 按模型分组聚合（sessions.json 中每个 session 有 model 字段）
            per_model_data = {}
            for s in agents:
                model = s.get("model", "unknown")
                provider = s.get("modelProvider", "")
                model_display = f"{model} ({provider})" if provider else model
                inp = s.get("inputTokens", 0) or 0
                out = s.get("outputTokens", 0) or 0
                cache = s.get("cacheRead", 0) or 0
                if model_display not in per_model_data:
                    per_model_data[model_display] = {"input": 0, "output": 0, "calls": 0, "cache": 0}
                per_model_data[model_display]["input"] += inp
                per_model_data[model_display]["output"] += out
                per_model_data[model_display]["cache"] += cache
                per_model_data[model_display]["calls"] += 1

            total_input = sum(d["input"] for d in per_model_data.values())
            total_output = sum(d["output"] for d in per_model_data.values())
            total_cache = sum(d["cache"] for d in per_model_data.values())

            latest = max(agents, key=lambda s: s.get("startedAt", 0) or s.get("updatedAt", 0))
            context = latest.get("contextTokens", DEFAULT_CONTEXT)

            models_sorted = sorted(per_model_data.keys())
            per_model_list = []
            raw_lines = ["📊 OpenClaw"]
            for mn in models_sorted:
                md = per_model_data[mn]
                per_model_list.append({
                    "model": mn, "input": md["input"], "output": md["output"],
                    "calls": md["calls"], "cache": md["cache"],
                })
                cw = context
                if from_ts is not None or to_ts is not None:
                    line = format_model_line(mn, md["input"], md["output"], md["cache"],
                                              md["calls"], session_count=md["calls"])
                else:
                    line = format_model_line(mn, md["input"], md["output"], md["cache"],
                                              md["calls"], context_window=cw)
                if line:
                    raw_lines.append(line)

            raw = "\n".join(raw_lines)
            model_list = ", ".join(models_sorted)
            stats = {
                "model": model_list,
                "input_tokens": total_input,
                "output_tokens": total_output,
                "cache_read": total_cache,
                "total_tokens": total_input + total_output,
                "context_window": context,
                "agent_count": len(agents),
            }
            if from_ts is None and to_ts is None:
                stats["context_pct"] = round((total_input + total_output) / context * 100, 1) if context else 0

            return AgentData(name="openclaw", display_name="OpenClaw",
                             stats=stats, raw=raw, per_model=per_model_list)

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
    print("\n🔍 选择你要查看的 AI 助手：")
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
#  导出
# ═══════════════════════════════════════════════════

def export_interactive(data: AgentData, agent: BaseAgent):
    """交互式导出统计"""
    try:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")

        # 获取今日总调用次数（全局 + 按模型）
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today_calls = 0
        today_calls_by_model = {}
        try:
            today_data = agent.collect(from_ts=today_start)
            if today_data.stats:
                today_calls = today_data.stats.get("api_calls", 0) or 0
                # Fallback: sum from per_model
                if today_calls == 0 and today_data.per_model:
                    today_calls = sum(pm.get("calls", 0) for pm in today_data.per_model)
            if today_data and today_data.per_model:
                for pm in today_data.per_model:
                    m = (pm.get("model", "") or "").strip()
                    if m:
                        today_calls_by_model[m] = pm.get("calls", 0)
        except Exception:
            today_calls = 0

        # ── 显示格式化汇总 ──
        print()
        print(f"📊 {data.display_name} — 导出 ({date_str})")
        print("═" * 52)
        filtered_models = [pm for pm in (data.per_model or []) if not _skip_model(pm)]
        for pm in filtered_models:
            m = pm.get("model", "unknown")
            inp = pm.get("input", 0)
            out = pm.get("output", 0)
            cache = pm.get("cache", 0)
            calls = pm.get("calls", 0)
            total_tok = inp + out
            total_w_cache = total_tok + cache
            print(f"  {m}")
            if agent._has_live_context:
                cw = detect_context(m)
                pct = round(total_tok / cw * 100, 1) if cw else 0
                print(f"    上下文          {fmt_num(total_tok):>8} / {fmt_num(cw):<8} ({pct}%)")
            else:
                print(f"    总计 tokens     {fmt_num(total_tok):>8}")
            print(f"    输入 tokens     {fmt_num(inp):>8}")
            print(f"    输出 tokens     {fmt_num(out):>8}")
            print(f"    缓存 tokens     {fmt_num(cache):>8}")
            print(f"    调用次数        {calls} 次 (今日: {today_calls_by_model.get(m, 0)} 次)")
            print(f"    ─────────────────────────────────────")
            print(f"    总计 tokens     {fmt_num(total_tok):>8}")
            print(f"    总计 + 缓存     {fmt_num(total_w_cache):>8}")

        # ── 合计（多模型时显示） ──
        if filtered_models and len(filtered_models) > 1:
            ti = sum(pm.get("input", 0) for pm in filtered_models)
            to = sum(pm.get("output", 0) for pm in filtered_models)
            tc = sum(pm.get("cache", 0) for pm in filtered_models)
            tca = sum(pm.get("calls", 0) for pm in filtered_models)
            tt = ti + to
            print(f"  {'─' * 42}")
            print(f"  合计")
            print(f"    输入 tokens     {fmt_num(ti):>8}")
            print(f"    输出 tokens     {fmt_num(to):>8}")
            print(f"    缓存 tokens     {fmt_num(tc):>8}")
            print(f"    调用次数        {tca} 次")
            print(f"    ─────────────────────────────────────")
            print(f"    总计 tokens     {fmt_num(tt):>8}")
            print(f"    总计 + 缓存     {fmt_num(tt + tc):>8}")
        print()

        # Step 1: 输入目录
        while True:
            dir_input = input("\n请输入导出目录路径: ").strip()
            if not dir_input or dir_input.lower() == "q":
                print("已取消导出")
                return
            dir_path = os.path.expanduser(dir_input)
            if os.path.isdir(dir_path):
                break
            print(f"⚠️ 目录不存在: {dir_path}")
            print("请确保目录存在，或输入 q 取消")

        # Step 2: 选择格式
        print("\n选择导出格式:")
        print("  [1] JSON")
        print("  [2] CSV")
        fmt_choice = input("请选择 (1/2): ").strip().lower()

        if fmt_choice in ("1", "json"):
            fmt = "json"
        elif fmt_choice in ("2", "csv"):
            fmt = "csv"
        else:
            print(f"⚠️ 不支持格式 '{fmt_choice}'，默认使用 JSON")
            fmt = "json"

        # Step 3: 写文件
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"token-stats_{agent.name()}_{timestamp}.{fmt}"
        filepath = os.path.join(dir_path, filename)

        if fmt == "json":
            export_data = {
                "tool": "token-stats",
                "version": VERSION,
                "agent": agent.name(),
                "agent_display": agent.display_name(),
                "export_date": date_str,
                "exported_at": now.isoformat(),
                "today_calls": today_calls,
                "per_model": [{
                    "model": pm.get("model", "unknown"),
                    "input_tokens": pm.get("input", 0),
                    "output_tokens": pm.get("output", 0),
                    "cache_tokens": pm.get("cache", 0),
                    "calls": pm.get("calls", 0),
                    "today_calls": today_calls_by_model.get(pm.get("model", ""), 0),
                    "total_tokens": pm.get("input", 0) + pm.get("output", 0),
                    "total_with_cache": pm.get("input", 0) + pm.get("output", 0) + pm.get("cache", 0),
                } for pm in filtered_models],
                "summary": (
                    {
                        "total_input_tokens": sum(pm.get("input", 0) for pm in filtered_models),
                        "total_output_tokens": sum(pm.get("output", 0) for pm in filtered_models),
                        "total_cache_tokens": sum(pm.get("cache", 0) for pm in filtered_models),
                        "total_calls": sum(pm.get("calls", 0) for pm in filtered_models),
                        "total_tokens": sum(pm.get("input", 0) + pm.get("output", 0) for pm in filtered_models),
                        "total_with_cache": sum(pm.get("input", 0) + pm.get("output", 0) + pm.get("cache", 0) for pm in filtered_models),
                    }
                    if filtered_models and len(filtered_models) > 1
                    else None
                ),
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        else:
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["模型", "输入tokens", "输出tokens", "缓存tokens",
                                 "调用次数", "今日总调用", "总计tokens", "总计+缓存"])
                for pm in filtered_models:
                    inp = pm.get("input", 0)
                    out = pm.get("output", 0)
                    cache = pm.get("cache", 0)
                    writer.writerow([
                        pm.get("model", "unknown"),
                        inp, out, cache,
                        pm.get("calls", 0), today_calls_by_model.get(pm.get("model", ""), 0),
                        inp + out, inp + out + cache,
                    ])

                if filtered_models and len(filtered_models) > 1:
                    ti = sum(pm.get("input", 0) for pm in filtered_models)
                    to = sum(pm.get("output", 0) for pm in filtered_models)
                    tc = sum(pm.get("cache", 0) for pm in filtered_models)
                    tca = sum(pm.get("calls", 0) for pm in filtered_models)
                    writer.writerow(["合计", ti, to, tc, tca, today_calls,
                                    ti + to, ti + to + tc])

        print(f"✅ 已导出到: {filepath}")
    except KeyboardInterrupt:
        print()
        print("已取消导出")


def export_multi(results: list[tuple[BaseAgent, AgentData]]):
    """导出多个 Agent 的统计（合并输出）"""
    try:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")

        # 收集每个 Agent 的今日数据
        agent_data_list = []
        for agent, data in results:
            today_calls = 0
            today_calls_by_model = {}
            try:
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                today_data = agent.collect(from_ts=today_start)
                if today_data.stats:
                    today_calls = today_data.stats.get("api_calls", 0) or 0
                    if today_calls == 0 and today_data.per_model:
                        today_calls = sum(pm.get("calls", 0) for pm in today_data.per_model)
                if today_data and today_data.per_model:
                    for pm in today_data.per_model:
                        m = (pm.get("model", "") or "").strip()
                        if m:
                            today_calls_by_model[m] = pm.get("calls", 0)
            except Exception:
                pass
            agent_data_list.append((agent, data, today_calls, today_calls_by_model))

        # ── 显示格式化汇总 ──
        print()
        print(f"📊 多 Agent 导出 ({date_str})")
        print("═" * 52)
        grand_ti = grand_to = grand_tc = grand_tca = grand_today = 0
        for agent, data, today_calls, today_calls_by_model in agent_data_list:
            print(f"\n  🤖 {agent.display_name()}")
            agent_models = [pm for pm in (data.per_model or []) if not _skip_model(pm)]
            for pm in agent_models:
                m = pm.get("model", "unknown")
                inp = pm.get("input", 0)
                out = pm.get("output", 0)
                cache = pm.get("cache", 0)
                calls = pm.get("calls", 0)
                total_tok = inp + out
                total_w_cache = total_tok + cache
                print(f"    {m}")
                if agent._has_live_context:
                    cw = detect_context(m)
                    pct = round(total_tok / cw * 100, 1) if cw else 0
                    print(f"      上下文          {fmt_num(total_tok):>8} / {fmt_num(cw):<8} ({pct}%)")
                print(f"      输入 tokens     {fmt_num(inp):>8}")
                print(f"      输出 tokens     {fmt_num(out):>8}")
                print(f"      缓存 tokens     {fmt_num(cache):>8}")
                print(f"      调用次数        {calls} 次 (今日: {today_calls_by_model.get(m, 0)} 次)")
                print(f"      ─────────────────────────────────────")
                print(f"      总计 tokens     {fmt_num(total_tok):>8}")
                print(f"      总计 + 缓存     {fmt_num(total_w_cache):>8}")

            # Agent 内合计
            if agent_models and len(agent_models) > 1:
                ti = sum(pm.get("input", 0) for pm in agent_models)
                to = sum(pm.get("output", 0) for pm in agent_models)
                tc = sum(pm.get("cache", 0) for pm in agent_models)
                tca = sum(pm.get("calls", 0) for pm in agent_models)
                tt = ti + to
                print(f"    {'─' * 42}")
                print(f"    合计")
                print(f"      输入 tokens     {fmt_num(ti):>8}")
                print(f"      输出 tokens     {fmt_num(to):>8}")
                print(f"      缓存 tokens     {fmt_num(tc):>8}")
                print(f"      调用次数        {tca} 次")
                print(f"      ─────────────────────────────────────")
                print(f"      总计 tokens     {fmt_num(tt):>8}")
                print(f"      总计 + 缓存     {fmt_num(tt + tc):>8}")
                grand_ti += ti; grand_to += to; grand_tc += tc; grand_tca += tca; grand_today += today_calls
            else:
                pm = agent_models[0] if agent_models else {}
                grand_ti += pm.get("input", 0)
                grand_to += pm.get("output", 0)
                grand_tc += pm.get("cache", 0)
                grand_tca += pm.get("calls", 0)
                grand_today += today_calls

        # 所有 Agent 总计
        if len(agent_data_list) > 1:
            gtt = grand_ti + grand_to
            print(f"\n  {'═' * 42}")
            print(f"  全部 Agent 总计")
            print(f"    输入 tokens     {fmt_num(grand_ti):>8}")
            print(f"    输出 tokens     {fmt_num(grand_to):>8}")
            print(f"    缓存 tokens     {fmt_num(grand_tc):>8}")
            print(f"    调用次数        {grand_tca} 次 (今日: {grand_today} 次)")
            print(f"    ─────────────────────────────────────")
            print(f"    总计 tokens     {fmt_num(gtt):>8}")
            print(f"    总计 + 缓存     {fmt_num(gtt + grand_tc):>8}")

        # Step 1: 输入目录
        while True:
            dir_input = input("\n请输入导出目录路径: ").strip()
            if not dir_input or dir_input.lower() == "q":
                print("已取消导出")
                return
            dir_path = os.path.expanduser(dir_input)
            if os.path.isdir(dir_path):
                break
            print(f"  {dir_path}")
            print("请确保目录存在，或输入 q 取消")

        # Step 2: 选择格式
        print("\n选择导出格式:")
        print("  [1] JSON")
        print("  [2] CSV")
        fmt_choice = input("请选择 (1/2): ").strip().lower()

        if fmt_choice in ("1", "json"):
            fmt = "json"
        elif fmt_choice in ("2", "csv"):
            fmt = "csv"
        else:
            print(f"  '{fmt_choice}'，默认使用 JSON")
            fmt = "json"

        # Step 3: 写文件
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        agent_names = "+".join(agent.name() for agent, _, _, _ in agent_data_list)
        filename = f"token-stats_{agent_names}_{timestamp}.{fmt}"
        filepath = os.path.join(dir_path, filename)

        if fmt == "json":
            agents_json = []
            for agent, data, today_calls, today_calls_by_model in agent_data_list:
                agent_models = [pm for pm in (data.per_model or []) if not _skip_model(pm)]
                per_model = [{
                    "model": pm.get("model", "unknown"),
                    "input_tokens": pm.get("input", 0),
                    "output_tokens": pm.get("output", 0),
                    "cache_tokens": pm.get("cache", 0),
                    "calls": pm.get("calls", 0),
                    "today_calls": today_calls_by_model.get(pm.get("model", ""), 0),
                    "total_tokens": pm.get("input", 0) + pm.get("output", 0),
                    "total_with_cache": pm.get("input", 0) + pm.get("output", 0) + pm.get("cache", 0),
                } for pm in agent_models]
                entry = {
                    "agent": agent.name(),
                    "agent_display": agent.display_name(),
                    "today_calls": today_calls,
                    "per_model": per_model,
                }
                if agent_models and len(agent_models) > 1:
                    entry["summary"] = {
                        "total_input_tokens": sum(pm.get("input", 0) for pm in agent_models),
                        "total_output_tokens": sum(pm.get("output", 0) for pm in agent_models),
                        "total_cache_tokens": sum(pm.get("cache", 0) for pm in agent_models),
                        "total_calls": sum(pm.get("calls", 0) for pm in agent_models),
                        "total_tokens": sum(pm.get("input", 0) + pm.get("output", 0) for pm in agent_models),
                        "total_with_cache": sum(pm.get("input", 0) + pm.get("output", 0) + pm.get("cache", 0) for pm in agent_models),
                    }
                agents_json.append(entry)

            export_data = {
                "tool": "token-stats",
                "version": VERSION,
                "export_date": date_str,
                "exported_at": now.isoformat(),
                "agents": agents_json,
            }
            if len(agent_data_list) > 1:
                export_data["grand_total"] = {
                    "total_input_tokens": grand_ti,
                    "total_output_tokens": grand_to,
                    "total_cache_tokens": grand_tc,
                    "total_calls": grand_tca,
                    "today_calls": grand_today,
                    "total_tokens": grand_ti + grand_to,
                    "total_with_cache": grand_ti + grand_to + grand_tc,
                }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        else:
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Agent", "模型", "输入tokens", "输出tokens", "缓存tokens",
                                "调用次数", "今日总调用", "总计tokens", "总计+缓存"])
                for agent, data, today_calls, today_calls_by_model in agent_data_list:
                    agent_models = [pm for pm in (data.per_model or []) if not _skip_model(pm)]
                    for pm in agent_models:
                        inp = pm.get("input", 0)
                        out = pm.get("output", 0)
                        cache = pm.get("cache", 0)
                        writer.writerow([
                            agent.name(), pm.get("model", "unknown"),
                            inp, out, cache,
                            pm.get("calls", 0), today_calls_by_model.get(pm.get("model", ""), 0),
                            inp + out, inp + out + cache,
                        ])
                    if agent_models and len(agent_models) > 1:
                        ti = sum(pm.get("input", 0) for pm in agent_models)
                        to = sum(pm.get("output", 0) for pm in agent_models)
                        tc = sum(pm.get("cache", 0) for pm in agent_models)
                        tca = sum(pm.get("calls", 0) for pm in agent_models)
                        writer.writerow([agent.name(), "合计", ti, to, tc, tca, today_calls,
                                       ti + to, ti + to + tc])
                if len(agent_data_list) > 1:
                    writer.writerow(["全部", "总计", grand_ti, grand_to, grand_tc, grand_tca,
                                   grand_today, grand_ti + grand_to, grand_ti + grand_to + grand_tc])

        print(f"  {filepath}")
        print(f"多 Agent 数据已合并导出")
    except KeyboardInterrupt:
        print()
        print("已取消导出")


# ═══════════════════════════════════════════════════
#  对比
# ═══════════════════════════════════════════════════

def run_compare(agent: BaseAgent, a_label: str, b_label: str):
    """对比两个时间段的统计"""
    a_start, a_end = parse_time_label(a_label)
    b_start, b_end = parse_time_label(b_label)

    data_a = agent.collect(from_ts=a_start, to_ts=a_end)
    data_b = agent.collect(from_ts=b_start, to_ts=b_end)

    models_a = {pm["model"]: pm for pm in (data_a.per_model or [])}
    models_b = {pm["model"]: pm for pm in (data_b.per_model or [])}
    all_models = sorted(set(list(models_a.keys()) + list(models_b.keys())))

    if not all_models:
        print("两个时间段均无数据")
        return

    a_disp = label_to_display(a_label)
    b_disp = label_to_display(b_label)
    print(f"\n📊 对比: {a_disp} vs {b_disp}  [{agent.display_name()}]")

    # 动态列宽：先扫一遍数据，取各列最宽值
    col_model = max(_display_width("模型"), max(_display_width(mn) for mn in all_models))
    col_delta = _display_width("变化")
    label_w = max(_display_width(a_disp), _display_width(b_disp), 6)

    # 预计算格式化后的数据宽度
    for mn in all_models:
        ma = models_a.get(mn, {"input": 0, "output": 0, "calls": 0, "cache": 0})
        mb = models_b.get(mn, {"input": 0, "output": 0, "calls": 0, "cache": 0})
        ta = ma["input"] + ma["output"]
        tb = mb["input"] + mb["output"]
        if ta == 0 and tb == 0:
            continue
        label_w = max(label_w, _display_width(fmt_num(ta)), _display_width(fmt_num(tb)))
        delta = tb - ta
        ds = f"+{fmt_num(delta)}" if delta > 0 else fmt_num(delta) if delta < 0 else "0"
        col_delta = max(col_delta, _display_width(ds))

    # 总计行也要纳入宽度计算
    col_model = max(col_model, _display_width("总计"))

    sep_w = _display_width(" | ")
    total_w = 2 + col_model + sep_w + label_w + sep_w + label_w + sep_w + col_delta
    print("═" * (total_w // 1))
    print(f"  {_pad_to('模型', col_model)} | {_pad_to(a_disp, label_w, '>')} | {_pad_to(b_disp, label_w, '>')} | {_pad_to('变化', col_delta, '>')}")
    print("─" * (total_w // 1))

    total_a, total_b = 0, 0
    model_count = 0
    for mn in all_models:
        ma = models_a.get(mn, {"input": 0, "output": 0, "calls": 0, "cache": 0})
        mb = models_b.get(mn, {"input": 0, "output": 0, "calls": 0, "cache": 0})
        ta = ma["input"] + ma["output"]
        tb = mb["input"] + mb["output"]
        if ta == 0 and tb == 0:
            continue
        total_a += ta
        total_b += tb
        delta = tb - ta
        ds = f"+{fmt_num(delta)}" if delta > 0 else fmt_num(delta) if delta < 0 else "0"
        print(f"  {_pad_to(mn, col_model)} | {_pad_to(fmt_num(ta), label_w, '>')} | {_pad_to(fmt_num(tb), label_w, '>')} | {_pad_to(ds, col_delta, '>')}")
        model_count += 1

    if model_count == 0:
        print("  (两侧均无有效数据)")
        print()
        return

    print("─" * (total_w // 1))
    total_delta = total_b - total_a
    total_delta_str = f"+{fmt_num(total_delta)}" if total_delta > 0 else fmt_num(total_delta) if total_delta < 0 else "0"
    print(f"  {_pad_to('总计', col_model)} | {_pad_to(fmt_num(total_a), label_w, '>')} | {_pad_to(fmt_num(total_b), label_w, '>')} | {_pad_to(total_delta_str, col_delta, '>')}")
    print()


# ═══════════════════════════════════════════════════
#  全部统计 (--all)
# ═══════════════════════════════════════════════════

def show_all(*, from_ts: float = None, to_ts: float = None):
    """显示本机所有 Agent 的统计"""
    installed = detect_installed()
    if not installed:
        print("❌ 本机未检测到任何支持的 AI 助手")
        return

    print("\n📊 本机 Agent 统计汇总")
    print("═" * 50)

    any_data = False
    for cls in ALL_AGENTS:
        detected = cls.detect()
        status = "✅" if detected else "❌"
        name = cls.display_name()
        print(f"\n{status} {name}")

        if detected:
            try:
                agent = cls()
                data = agent.collect(from_ts=from_ts, to_ts=to_ts)
                if data.stats:
                    any_data = True
                print(data.raw)
            except Exception as e:
                msg = str(e)
                if "locked" in msg.lower():
                    msg = "数据库被锁定（Agent 正在运行，请先关闭 Agent）"
                print(f"  ⚠️ 读取失败: {msg}")
        else:
            print("  (未安装)")

    if not any_data:
        print("\n（所有 Agent 均无数据）")
    print()


# ═══════════════════════════════════════════════════
#  PATH 管理（--setup / --uninstall 共用）
# ═══════════════════════════════════════════════════

PATH_MARKER_START = "# >>> token-stats PATH >>>"
PATH_MARKER_END = "# <<< token-stats PATH <<<"


def _add_to_path_windows(bin_dir):
    """将目录添加到用户 PATH（注册表），广播变更消息。返回 True/False。"""
    import ctypes
    import winreg
    key = None
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE)
        try:
            current, _ = winreg.QueryValueEx(key, "PATH")
        except FileNotFoundError:
            current = ""
        entries = [e for e in current.split(";") if e]
        if bin_dir in entries:
            return False
        entries.append(bin_dir)
        new_path = ";".join(entries)
        winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 2, 5000, None)
        return True
    except Exception:
        return False
    finally:
        if key is not None:
            winreg.CloseKey(key)


def _remove_from_path_windows(bin_dir):
    """从用户 PATH 中移除目录（注册表），广播变更消息。"""
    import ctypes
    import winreg
    key = None
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE)
        current, _ = winreg.QueryValueEx(key, "PATH")
        entries = [e for e in current.split(";") if e and e != bin_dir]
        new_path = ";".join(entries)
        winreg.SetValueEx(key, "PATH", 0, winreg.REG_EXPAND_SZ, new_path)
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 2, 5000, None)
        return True
    except Exception:
        return False
    finally:
        if key is not None:
            winreg.CloseKey(key)


def _add_to_path_unix(bin_dir, rc_file):
    """将 export PATH 行（带标记）追加到 shell 配置文件。若已存在则跳过。"""
    rc_path = os.path.expanduser(rc_file)
    export_line = f'export PATH="$PATH:{bin_dir}"'
    block = f"\n{PATH_MARKER_START}\n{export_line}\n{PATH_MARKER_END}\n"
    try:
        if os.path.exists(rc_path):
            with open(rc_path, "r", encoding="utf-8") as f:
                if PATH_MARKER_START in f.read():
                    return False  # 已存在，跳过
        with open(rc_path, "a", encoding="utf-8") as f:
            f.write(block)
        return True
    except Exception:
        return False


def _remove_from_path_unix(bin_dir, rc_file):
    """从 shell 配置文件中移除 token-stats PATH 标记块。"""
    rc_path = os.path.expanduser(rc_file)
    if not os.path.exists(rc_path):
        return False
    try:
        with open(rc_path, "r", encoding="utf-8") as f:
            content = f.read()
        pattern = f"\n{PATH_MARKER_START}\nexport PATH=\"$PATH:{bin_dir}\"\n{PATH_MARKER_END}\n"
        if pattern in content:
            content = content.replace(pattern, "")
        # also try without leading newline (at file start)
        pattern2 = f"{PATH_MARKER_START}\nexport PATH=\"$PATH:{bin_dir}\"\n{PATH_MARKER_END}\n"
        if pattern2 in content:
            content = content.replace(pattern2, "")
        with open(rc_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════
#  CLI 入口
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="token-stats — 选个 Agent 看它的 token 消耗",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
命令大全:
  基础:
    token-stats                       交互式菜单选择 Agent → 查看统计
    token-stats -a <name>             直接指定 Agent: hermes/claude-code/codex/openclaw
    token-stats --version             显示版本号
    token-stats -a <name> --detail    详细模式（同默认）
    token-stats -a <name> --now       当前快照（同默认）

  快速时间段:
    token-stats -a <name> --today     今日统计
    token-stats -a <name> --yesterday 昨日统计
    token-stats -a <name> --week      本周统计（周一起）
    token-stats -a <name> --last-7d   最近 7 天
    token-stats -a <name> --from 2025-01-01 --to 2025-01-31  自定义时间段

  对比:
    token-stats -a <name> --compare --a today --b yesterday
        快捷标签对比
    token-stats -a <name> --compare --a 2025-01-01~2025-01-07 --b 2025-01-08~2025-01-14
        自定义时间段对比
    标签支持: today / yesterday / this-week / last-week / YYYY-MM-DD / YYYY-MM-DD~YYYY-MM-DD

  导出:
    token-stats -a <name> --export    导出当前统计（交互式选目录和格式）
    token-stats -a <name> --today --export  导出今日统计

  实时监控:
    token-stats -a <name> --watch     实时监控，每 5 秒刷新 (Ctrl+C 停止)
    token-stats -a <name> --watch 10  自定义间隔秒数
    停止后自动展示监控时间段内的完整统计数据（模型、输入、输出、缓存、调用次数）

  多 Agent:
    token-stats --all                 查看本机所有 Agent 统计
    token-stats --list-backends       列出已安装的 Agent

  安装与卸载:
    clawhub install agent-usage-stats  从 ClawHub 安装
    token-stats --setup                创建全局命令 + 自动加入 PATH
    token-stats --uninstall            删除全局命令 + 自动清理 PATH
        """,
    )
    parser.add_argument("--version", action="store_true", help="显示版本号")
    parser.add_argument("--list-backends", action="store_true", help="列出本机已安装的 Agent")
    parser.add_argument("-a", "--agent", help="直接指定 Agent: hermes/claude-code/codex/openclaw")
    parser.add_argument("--watch", nargs="?", type=int, const=5, default=None, metavar="秒",
                        help="实时监控模式（默认每 5 秒轮询）")
    parser.add_argument("setup_pos", nargs="?", const=True, help=argparse.SUPPRESS)

    # 时间段
    parser.add_argument("--today", action="store_true", help="今日统计")
    parser.add_argument("--yesterday", action="store_true", help="昨日统计")
    parser.add_argument("--week", action="store_true", help="本周统计")
    parser.add_argument("--last-7d", action="store_true", help="最近 7 天统计")
    parser.add_argument("--from", dest="from_date", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="结束日期 (YYYY-MM-DD)")

    # 功能
    parser.add_argument("--export", nargs="?", const=True, default=None, metavar="目录",
                        help="导出统计（交互式选择目录和格式）")
    parser.add_argument("--compare", action="store_true", help="对比模式")
    parser.add_argument("--a", help="对比时间段 A（today/yesterday/this-week/last-week/日期/日期段）")
    parser.add_argument("--b", help="对比时间段 B")
    parser.add_argument("--detail", action="store_true", help="详细信息模式")
    parser.add_argument("--now", action="store_true", help="当前快照（同默认）")
    parser.add_argument("--all", action="store_true", help="查看本机所有 Agent 统计")
    parser.add_argument("--setup", action="store_true", help="创建 ~/.local/bin/token-stats 并自动加入 PATH")
    parser.add_argument("--uninstall", action="store_true", help="删除全局命令并清理 PATH")

    args = parser.parse_args()

    # 兼容旧用法：token-stats setup / uninstall → 当作 --setup / --uninstall
    if args.setup_pos is True or args.setup_pos == "setup":
        args.setup = True
    if args.setup_pos == "uninstall":
        args.uninstall = True

    # ── version ──
    if args.version:
        print(f"token-stats v{VERSION}")
        return

    # ── setup ──
    if args.setup:
        is_win = sys.platform == "win32"
        is_mac = sys.platform == "darwin"
        bin_dir = os.path.join(os.path.expanduser("~"), ".local", "bin")
        script_path = os.path.abspath(__file__)
        os.makedirs(bin_dir, exist_ok=True)

        # 1. 创建包装器
        if is_win:
            target = os.path.join(bin_dir, "token-stats.cmd")
            wrapper = f'@python "{script_path}" %*\n'
            with open(target, "w", encoding="utf-8") as f:
                f.write(wrapper)
        else:
            target = os.path.join(bin_dir, "token-stats")
            wrapper = (
                "#!/bin/sh\n"
                f'exec python3 "{script_path}" "$@"\n'
            )
            with open(target, "w", encoding="utf-8") as f:
                f.write(wrapper)
            os.chmod(target, 0o755)

        print(f"✅ 已创建全局命令: {target}")

        # 2. 自动添加 PATH
        print("⏳ 正在添加到系统 PATH...", end="", flush=True)
        path_ok = bin_dir in os.environ.get("PATH", "").split(os.pathsep)
        if not path_ok:
            if is_win:
                _add_to_path_windows(bin_dir)
            elif is_mac:
                _add_to_path_unix(bin_dir, "~/.zshrc")
            else:
                _add_to_path_unix(bin_dir, "~/.bashrc")
        print("\r✅ 已添加到系统 PATH                    ")

        # 3. 检查旧 alias（仅 Unix）
        if not is_win:
            for rc_file in ["~/.zshrc", "~/.bashrc", "~/.bash_profile"]:
                rc_path = os.path.expanduser(rc_file)
                if os.path.exists(rc_path):
                    with open(rc_path, encoding="utf-8") as f:
                        content = f.read()
                    alias_lines = []
                    for i, line in enumerate(content.splitlines(), 1):
                        if "alias token-stats" in line.strip():
                            alias_lines.append(f"  {rc_file} 第 {i} 行: {line.strip()}")
                    if alias_lines:
                        print()
                        print("⚠️  检测到旧的 alias，会覆盖全局命令，建议删除：")
                        for al in alias_lines:
                            print(al)
                        print("   删除方法: 手动编辑或用 sed 删除对应行，然后 source ~/.zshrc")

        # 4. 扫描并保存 Agent 数据路径
        agent_paths = _scan_all_agent_paths()
        if agent_paths:
            _save_agent_paths(agent_paths)
            detected = []
            for key in agent_paths:
                label = key.replace("_dir", "").replace("_db", "").replace("_sessions", "")
                detected.append(label.capitalize())
            print(f"✅ 已自动检测并保存 Agent 路径: {', '.join(sorted(set(detected)))}")
        else:
            print("ℹ️  未检测到任何 Agent 数据文件，运行后会自动尝试标准路径")

        print()
        print("现在可以在新终端窗口中直接运行: token-stats --version")
        return

    # ── uninstall ──
    if args.uninstall:
        is_win = sys.platform == "win32"
        is_mac = sys.platform == "darwin"
        bin_dir = os.path.join(os.path.expanduser("~"), ".local", "bin")

        # 1. 删除包装器
        if is_win:
            target = os.path.join(bin_dir, "token-stats.cmd")
        else:
            target = os.path.join(bin_dir, "token-stats")
        if os.path.exists(target):
            os.remove(target)
            print(f"✅ 已删除: {target}")
        else:
            print(f"ℹ️  全局命令不存在: {target}")

        # 2. 清理 PATH
        print("⏳ 正在清理系统 PATH...", end="", flush=True)
        if is_win:
            _remove_from_path_windows(bin_dir)
        elif is_mac:
            _remove_from_path_unix(bin_dir, "~/.zshrc")
        else:
            _remove_from_path_unix(bin_dir, "~/.bashrc")
        print("\r✅ 已清理系统 PATH                    ")

        # 3. 清理配置文件
        config_dir = os.path.join(os.path.expanduser("~"), ".config", "token-stats")
        if os.path.exists(config_dir):
            import shutil
            shutil.rmtree(config_dir, ignore_errors=True)
            print(f"✅ 已清理配置文件: {config_dir}")

        print()
        print("卸载完成。如需彻底删除技能文件，请执行: clawhub uninstall agent-usage-stats")
        return

    # ── list-backends ──
    if args.list_backends:
        print("\n本机已安装的 AI 助手：")
        for cls in ALL_AGENTS:
            ok = "✅" if cls.detect() else "❌"
            print(f"  {ok} {cls.display_name()}")
        print()
        return

    # ── 解析时间段参数 ──
    from_ts = None
    to_ts = None

    if args.from_date:
        if args.to_date:
            from_ts, _ = parse_date(args.from_date)
            _, to_ts = parse_date(args.to_date)
        else:
            from_ts, _ = parse_date(args.from_date)
            to_ts = from_ts + 86399  # end of that day
    elif args.to_date and not args.from_date:
        _, to_ts = parse_date(args.to_date)
        # no from_ts means "from beginning"

    if args.today:
        from_ts, to_ts = parse_time_label("today")
    elif args.yesterday:
        from_ts, to_ts = parse_time_label("yesterday")
    elif args.week:
        from_ts, to_ts = parse_time_label("this-week")
    elif args.last_7d:
        from_ts, to_ts = parse_time_label("last-7d")

    # ── Helper: collect agent data ──
    def _collect_agent_data(agents_list):
        results = []
        for agent in agents_list:
            try:
                data = agent.collect(from_ts=from_ts, to_ts=to_ts)
                results.append((agent, data))
            except Exception as e:
                print(f"❌ {agent.display_name()}: {e}")
        return results

    # ── --all (所有 Agent) ──
    if args.all:
        if args.watch is not None:
            print("⚠️ --watch 仅支持单个 Agent，请使用 -a <name> --watch")
            return
        if args.compare:
            print("⚠️ --compare 仅支持单个 Agent")
            return
        installed = detect_installed()
        if not installed:
            print("❌ 本机未检测到任何支持的 AI 助手")
            return
        agents = [cls() for cls in ALL_AGENTS if cls.detect()]
        if args.export:
            results = _collect_agent_data(agents)
            if results:
                export_multi(results)
        else:
            show_all(from_ts=from_ts, to_ts=to_ts)
        return

    # ── 选择 Agent(s) ──
    installed = detect_installed()
    if not installed:
        print("❌ 本机未检测到任何支持的 AI 助手")
        print("   支持的 Agent: Hermes, Claude Code, CodeX, OpenClaw")
        print("   请先使用并运行一个 Agent 后再来查看统计。")
        return

    if args.agent:
        backends = [b.strip() for b in args.agent.split(',')]
        agents = []
        for name in backends:
            try:
                agents.append(get_agent(name))
            except ValueError as e:
                print(f"❌ {e}")
                print(f"   可选: {', '.join(cls.name() for cls in ALL_AGENTS)}")
                return
        if len(agents) > 1:
            if args.watch is not None:
                print("⚠️ --watch 仅支持单个 Agent")
                return
            if args.compare:
                print("⚠️ --compare 仅支持单个 Agent")
                return
            results = _collect_agent_data(agents)
            if args.export:
                export_multi(results)
            else:
                for agent, data in results:
                    print(f"\n{'─'*50}")
                    print(f"  {agent.display_name()}")
                    print(f"{'─'*50}")
                    print(data.raw)
            return
        agent = agents[0]
    elif len(installed) == 1:
        agent = installed[0]()
        print(f"\n（本机仅安装了 {agent.display_name()}，直接显示统计）")
    else:
        agent = show_menu(installed)

    # ── --compare (对比) ──
    if args.compare:
        a_label = args.a
        b_label = args.b
        if not a_label or not b_label:
            print("❌ --compare 需要 --a 和 --b 参数")
            print("   示例: token-stats -a hermes --compare --a today --b yesterday")
            return
        run_compare(agent, a_label, b_label)
        return

    # ── --watch (实时监控) ──
    if args.watch is not None:
        agent.watch(args.watch)
        return

    # ── 收集并展示 ──
    try:
        data = agent.collect(from_ts=from_ts, to_ts=to_ts)
        print()
        print(data.raw)
        print()
    except Exception as e:
        print(f"❌ 获取 {agent.display_name()} 统计失败: {e}")
        return

    # ── --export (导出) ──
    if args.export:
        export_interactive(data, agent)

    # --detail 在下一步也可能有用，但当前 collect() 已含 per_model 详情
    # detail 主要用于 watch/collect 输出内容更丰富，当前 collect 实现已包含
    # 后续可通过 stats 或 per_model 扩展


if __name__ == "__main__":
    main()
