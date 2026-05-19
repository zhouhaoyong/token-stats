#!/usr/bin/env python3
"""
token-stats — 选个 Agent 看它的 token 消耗

用法:
  token-stats                    交互式菜单：选 Agent → 看统计
  token-stats -a hermes          直接查看 Hermes
  token-stats -w / --watch            交互式菜单 → 实时监控
  token-stats --all              查看本机所有 Agent 的统计
  token-stats -a hermes --now    同默认（显式快照）

  时间段查询:
  token-stats -a hermes -t / --today
  token-stats -a hermes -y / --yesterday
  token-stats -a hermes --week
  token-stats -a hermes --last-7d
  token-stats -a hermes -m / --month
  token-stats -a hermes --year
  token-stats -a hermes --from 2025-01-01 --to 2025-01-31

  导出:
  token-stats -a hermes -e / --export
  token-stats -a hermes -t -e

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

VERSION = "2.4.1"

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
        return None


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

def _fmt_float(v: float) -> str:
    """保留最多 2 位小数，去掉尾部多余的零。"""
    s = f"{v:.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def fmt_num(n: int) -> str:
    if abs(n) < 1000:
        return str(n)
    elif abs(n) < 1_000_000:
        return f"{_fmt_float(n/1000)}K"
    else:
        return f"{_fmt_float(n/1_000_000)}M"


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
        m, i, o, c, ca = models[0]
        t = i + o
        parts = [f"入 {fmt_num_fn(i)}",
                 f"出 {fmt_num_fn(o)}",
                 f"缓 {fmt_num_fn(c)}",
                 f"总计/+缓存 {fmt_num_fn(t)}/{fmt_num_fn(c)}",
                 f"调用 {ca} 次"]
        lines.append(f"  📅 今日 | {' | '.join(parts)}")
    else:
        rows = []
        for m, i, o, c, ca in models:
            t = i + o
            cols = [
                f"入 {fmt_num_fn(i)}",
                f"出 {fmt_num_fn(o)}",
                f"缓 {fmt_num_fn(c)}",
                f"总计/+缓存 {fmt_num_fn(t)}/{fmt_num_fn(c)}",
                f"调用 {ca} 次",
            ]
            rows.append((m, cols))
        cols_total = [
            f"入 {fmt_num_fn(ti)}",
            f"出 {fmt_num_fn(to)}",
            f"缓 {fmt_num_fn(tc)}",
            f"总计/+缓存 {fmt_num_fn(ti + to)}/{fmt_num_fn(tc)}",
            f"调用 {tca} 次",
        ]
        rows.append(("今日合计", cols_total))
        col_count = len(cols_total)
        col_widths = [0] * (col_count + 1)
        col_widths[0] = max(_display_width(r[0]) for r in rows)
        for ci in range(col_count):
            col_widths[ci + 1] = max(_display_width(r[1][ci]) for r in rows)
        lines.append("  📅 今日")
        for label, cols in rows:
            parts = [_pad_to(label, col_widths[0])]
            for ci, col_text in enumerate(cols):
                parts.append(_pad_to(col_text, col_widths[ci + 1], ">"))
            lines.append(f"    {' | '.join(parts)}")
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
    "qwen3.6-plus": 1_048_576,
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

    if s in ("this-month", "month"):
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), now.timestamp()

    if s == "last-month":
        first_of_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_last = first_of_this - timedelta(seconds=1)
        start_of_last = end_of_last.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_of_last.timestamp(), end_of_last.timestamp()

    if s in ("this-year", "year"):
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), now.timestamp()

    if s == "last-year":
        start = now.replace(year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(year=now.year - 1, month=12, day=31, hour=23, minute=59, second=59, microsecond=0)
        return start.timestamp(), end.timestamp()

    # Date range: YYYY-MM-DD~YYYY-MM-DD
    if "~" in s:
        parts = s.split("~", 1)
        start_ts, _ = parse_date(parts[0])
        _, end_ts = parse_date(parts[1])
        return start_ts, end_ts

    # Single date
    return parse_date(s)


def _split_months(from_ts, to_ts):
    """Split a time range into calendar month buckets.
    Returns [(label, start_ts, end_ts), ...]"""
    from_dt = datetime.fromtimestamp(from_ts)
    to_dt = datetime.fromtimestamp(to_ts)
    months = []
    current = from_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while current <= to_dt:
        month_start = current
        if current.month == 12:
            next_month = current.replace(year=current.year + 1, month=1)
        else:
            next_month = current.replace(month=current.month + 1)
        month_end = min(next_month - timedelta(seconds=1), to_dt)
        label = month_start.strftime('%Y-%m')
        months.append((label, month_start.timestamp(), month_end.timestamp()))
        current = next_month
    return months


def _progress_bar(pct: float) -> str:
    """10 段上下文进度条，带 ANSI 颜色。"""
    n = min(10, max(0, round(pct / 10)))
    bar = "█" * n + "░" * (10 - n)
    # ANSI 颜色：绿(<60%) / 黄(60-90%) / 红(>90%)
    if pct >= 90:
        color = "\033[31m"  # 红
    elif pct >= 60:
        color = "\033[33m"  # 黄
    else:
        color = "\033[32m"  # 绿
    return f"{color}[{bar}]\033[0m {pct}%"


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


def _strip_ansi(s: str) -> str:
    """移除 ANSI 转义序列，用于显示宽度计算。"""
    return re.sub(r'\033\[[0-9;]*m', '', s)


def _pad_ansi(s: str, width: int, align: str = "<") -> str:
    """按可见宽度填充（忽略 ANSI 码）。"""
    dw = _display_width(_strip_ansi(s))
    pad = max(0, width - dw)
    if align == ">":
        return " " * pad + s
    else:
        return s + " " * pad


def _align_rows(rows):
    """rows: list of list of str。每列按最大宽度左对齐，最后一列不补。"""
    if not rows:
        return rows
    n_cols = max(len(r) for r in rows)
    widths = [0] * n_cols
    for row in rows:
        for i, col in enumerate(row):
            w = _display_width(_strip_ansi(col))
            if w > widths[i]:
                widths[i] = w
    result = []
    for row in rows:
        padded = []
        for i, col in enumerate(row):
            if i < n_cols - 1:
                padded.append(_pad_ansi(col, widths[i], '<'))
            else:
                padded.append(col)
        result.append(padded)
    return result


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
    if s in ("this-month", "month"):
        start = now.replace(day=1)
        return f"{start.strftime('%Y-%m-%d')}~{now.strftime('%Y-%m-%d')}"
    if s == "last-month":
        first_of_this = now.replace(day=1)
        end_of_last = first_of_this - timedelta(days=1)
        return f"{end_of_last.replace(day=1).strftime('%Y-%m-%d')}~{end_of_last.strftime('%Y-%m-%d')}"
    if s in ("this-year", "year"):
        return f"{now.replace(month=1, day=1).strftime('%Y-%m-%d')}~{now.strftime('%Y-%m-%d')}"
    if s == "last-year":
        return f"{now.year - 1}-01-01~{now.year - 1}-12-31"
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
        parts.append(f"入 {fmt_num(inp)}")
        parts.append(f"出 {fmt_num(out)}")
        parts.append(f"缓 {fmt_num(cache)}")
        parts.append(f"总计/+缓存 {fmt_num(total)}/{fmt_num(cache)}")
    else:
        parts.append(f"入 {fmt_num(inp)}")
        parts.append(f"出 {fmt_num(out)}")
        parts.append(f"缓 {fmt_num(cache)}")
        parts.append(f"总计/+缓存 {fmt_num(total)}/{fmt_num(cache)}")
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
        bl_initial = {k: dict(v) for k, v in bl_models.items()}
        print("初始状态:")
        has_data = False
        has_cache = any(mv.get("cache", 0) for mv in bl_models.values())
        if bl_models:
            init_rows = []
            for mn, mv in bl_models.items():
                total = mv["input"] + mv["output"]
                cols = [mn]
                cache_val = mv.get('cache', 0)
                if self._has_live_context:
                    cw = detect_context(mn)
                    pct = round(total / cw * 100, 1) if cw else 0
                    cols.append(_progress_bar(pct))
                    cols.append(f"{fmt_num(total)}/{fmt_num(cw)}")
                cols.append(f"入 {fmt_num(mv['input'])}")
                cols.append(f"出 {fmt_num(mv['output'])}")
                cols.append(f"缓 {fmt_num(cache_val)}")
                cols.append(f"总计/+缓存 {fmt_num(total)}/{fmt_num(cache_val)}")
                cols.append(f"调用 {mv['calls']}")
                init_rows.append(cols)
                has_data = True
            aligned = _align_rows(init_rows)
            for row in aligned:
                print(f"  {' | '.join(row)}")
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

                # 增量行
                print("  ╌" * 20)
                # 先检查是否有任何模型有缓存数据（保证列一致）
                any_cache_now = any(
                    mv.get("cache", 0) or (mv.get("cache", 0) - bl_models.get(mn, {}).get("cache", 0))
                    for mn, mv in now_models.items()
                )
                delta_rows = []
                idle_models = []
                for mn, mv in now_models.items():
                    bl = bl_models.get(mn, {"input": 0, "output": 0, "calls": 0, "cache": 0})
                    d_in = mv["input"] - bl["input"]
                    d_out = mv["output"] - bl["output"]
                    d_tok = d_in + d_out
                    d_cache = mv.get("cache", 0) - bl.get("cache", 0)
                    d_calls = mv["calls"] - bl["calls"]
                    has_delta = d_tok > 0 or d_cache > 0 or d_calls > 0
                    total = mv["input"] + mv["output"]

                    if total == 0 and mv["calls"] == 0:
                        idle_models.append(mn)
                        bl_models[mn] = mv
                        continue

                    cols = [mn]
                    cache_v = mv.get('cache', 0)
                    if self._has_live_context:
                        cw = detect_context(mn)
                        pct = round(total / cw * 100, 1) if cw else 0
                        cols.append(_progress_bar(pct))
                        cols.append(f"{fmt_num(total)}/{fmt_num(cw)}")
                    if has_delta:
                        cols.append(f"+{fmt_num(d_in)}入/{fmt_num(mv['input'])}")
                        cols.append(f"+{fmt_num(d_out)}出/{fmt_num(mv['output'])}")
                        if any_cache_now:
                            cols.append(f"+{fmt_num(d_cache)}缓/{fmt_num(cache_v)}")
                        cols.append(f"+{d_calls}调用")
                    else:
                        cols.append(f"入 {fmt_num(mv['input'])}")
                        cols.append(f"出 {fmt_num(mv['output'])}")
                        if any_cache_now:
                            cols.append(f"缓 {fmt_num(cache_v)}")
                        cols.append(f"总计/+缓存 {fmt_num(total)}/{fmt_num(cache_v)}")
                        cols.append(f"调用 {mv['calls']}")

                    delta_rows.append((cols, has_delta, mn, mv))

                if delta_rows:
                    aligned = _align_rows([r[0] for r in delta_rows])
                    for (cols, has_delta, mn, mv), aligned_cols in zip(delta_rows, aligned):
                        print(f"  {' | '.join(aligned_cols)}")
                        if has_delta:
                            bl_models[mn] = mv
                if idle_models:
                    print(f"  (未使用: {', '.join(idle_models)})")
                print("  ╌" * 20)

                # 📅 今日合计
                try:
                    today_data = self.collect(from_ts=today_start)
                    print(f"  ╌╌╌╌╌ 📅 今日 ╌╌╌╌╌")
                    ti = to = tc = tca = 0
                    today_models = today_data.per_model or []
                    today_rows = []
                    today_has_cache = False
                    for pm in today_models:
                        m = pm.get("model", "?")
                        i = pm.get("input", 0) or 0
                        o = pm.get("output", 0) or 0
                        c = pm.get("cache", 0) or 0
                        ca = pm.get("calls", 0) or 0
                        if i == 0 and o == 0 and ca == 0:
                            continue
                        ti += i; to += o; tc += c; tca += ca
                        t = i + o
                        cols = [m, f"入 {fmt_num(i)}", f"出 {fmt_num(o)}",
                                f"缓 {fmt_num(c)}",
                                f"总计/+缓存 {fmt_num(t)}/{fmt_num(c)}", f"调用 {ca}"]
                        today_rows.append(cols)
                    if today_rows:
                        if len(today_models) > 1:
                            sum_row = ["今日合计", f"入 {fmt_num(ti)}", f"出 {fmt_num(to)}",
                                       f"缓 {fmt_num(tc)}",
                                       f"总计/+缓存 {fmt_num(ti + to)}/{fmt_num(tc)}", f"调用 {tca}"]
                            today_rows.append(sum_row)
                        aligned = _align_rows(today_rows)
                        for row in aligned:
                            print(f"  {' | '.join(row)}")
                    print("  ╌" * 20)
                except Exception:
                    pass
            else:
                print(f"── [{ts}] 无新活动 ──")

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
            final_rows = []
            for mn, mv in sorted(bl_models.items()):
                total = mv["input"] + mv["output"]
                cache_v = mv.get("cache", 0)
                cols = [mn]
                if self._has_live_context:
                    cw = detect_context(mn)
                    pct = round(total / cw * 100, 1) if cw else 0
                    cols.append(_progress_bar(pct))
                    cols.append(f"{fmt_num(total)}/{fmt_num(cw)}")
                cols.append(f"入 {fmt_num(mv['input'])}")
                cols.append(f"出 {fmt_num(mv['output'])}")
                cols.append(f"缓 {fmt_num(cache_v)}")
                cols.append(f"总计/+缓存 {fmt_num(total)}/{fmt_num(cache_v)}")
                cols.append(f"调用 {mv['calls']}")
                final_rows.append(cols)
            aligned = _align_rows(final_rows)
            for row in aligned:
                print(f"  {' | '.join(row)}")

            # 📅 今日累计
            try:
                today_data = self.collect(from_ts=today_start)
                ti = to = tc = tca = 0
                today_models = today_data.per_model or []
                today_rows = []
                for pm in today_models:
                    m = pm.get("model", "?")
                    i = pm.get("input", 0) or 0
                    o = pm.get("output", 0) or 0
                    c = pm.get("cache", 0) or 0
                    ca = pm.get("calls", 0) or 0
                    if i == 0 and o == 0 and ca == 0:
                        continue
                    ti += i; to += o; tc += c; tca += ca
                    t = i + o
                    cols = [m, f"入 {fmt_num(i)}", f"出 {fmt_num(o)}",
                            f"缓 {fmt_num(c)}",
                            f"总计/+缓存 {fmt_num(t)}/{fmt_num(c)}", f"调用 {ca}"]
                    today_rows.append(cols)
                if today_rows:
                    print(f"\n  ╌╌╌╌╌ 📅 今日累计 ╌╌╌╌╌")
                    if len(today_models) > 1:
                        sum_row = ["今日合计", f"入 {fmt_num(ti)}", f"出 {fmt_num(to)}",
                                   f"缓 {fmt_num(tc)}",
                                   f"总计/+缓存 {fmt_num(ti + to)}/{fmt_num(tc)}", f"调用 {tca}"]
                        today_rows.append(sum_row)
                    aligned = _align_rows(today_rows)
                    for row in aligned:
                        print(f"  {' | '.join(row)}")
                    print("  ╌" * 20)
            except Exception:
                pass

            # 总增量（最新累计 - 初始基线）
            total_d_tok = total_d_cache = total_d_calls = 0
            total_d_in = total_d_out = 0
            any_d_cache = False
            delta_data = []
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
                    if d_cache:
                        any_d_cache = True
                    delta_data.append((mn, d_tok, d_in, d_out, d_cache, d_calls))

            if delta_data:
                print(f"\n  监控期间增量:")
                print("  ╌" * 20)
                inc_rows = []
                for (mn, d_tok, d_in, d_out, d_cache, d_calls) in delta_data:
                    cols = [mn, f"+{fmt_num(d_tok)}总计", f"+{fmt_num(d_in)}入", f"+{fmt_num(d_out)}出"]
                    if any_d_cache:
                        cols.append(f"+{fmt_num(d_cache)}存")
                    cols.append(f"+{d_calls}调用")
                    inc_rows.append(cols)
                aligned = _align_rows(inc_rows)
                for row in aligned:
                    print(f"  {' | '.join(row)}")
                if len(delta_data) > 1:
                    sum_parts = [f"+{fmt_num(total_d_tok)}总计",
                                 f"+{fmt_num(total_d_in)}入",
                                 f"+{fmt_num(total_d_out)}出"]
                    if total_d_cache:
                        sum_parts.append(f"+{fmt_num(total_d_cache)}存")
                    sum_parts.append(f"+{total_d_calls}调用")
                    print(f"  增量合计 | {' | '.join(sum_parts)}")
                print("  ╌" * 20)
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
        conn = sqlite3.connect(hermes_db, timeout=10)
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
            conn = sqlite3.connect(db, timeout=5)
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

def show_menu(installed: list[type[BaseAgent]], *, allow_all: bool = True):
    """交互式菜单。返回 BaseAgent 实例 / 'all' / None(退出)。"""
    print("\n🔍 选择你要查看的 AI 助手：")
    print("─" * 40)
    for i, cls in enumerate(installed, 1):
        print(f"  [{i}] {cls.display_name()}")
    if allow_all:
        print("  [a] 所有")
    print("  [q] 退出")
    print("─" * 40)

    while True:
        try:
            choice = input("请选择：").strip().lower()
            if choice == "q":
                return None
            if allow_all and choice == "a":
                return "all"
            idx = int(choice) - 1
            if 0 <= idx < len(installed):
                return installed[idx]()
            valid = f"1-{len(installed)}"
            if allow_all:
                valid += "、a"
            valid += " 或 q"
            print(f"请输入 {valid}")
        except (ValueError, EOFError):
            valid = f"1-{len(installed)}"
            if allow_all:
                valid += "、a"
            valid += " 或 q"
            print(f"请输入 {valid}")


# ═══════════════════════════════════════════════════
#  导出 — 纯 stdlib XLSX 写入器 + 交互式导出函数
# ═══════════════════════════════════════════════════

import zipfile
import xml.etree.ElementTree as ET

_METRIC_LABELS = {'input': '输入', 'output': '输出', 'cache': '缓存',
                  'calls': '调用', 'total': '总计', 'total_with_cache': '总计(含缓存)'}
_METRIC_ORDER = ['input', 'output', 'cache', 'calls', 'total', 'total_with_cache']

_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ET.register_namespace('', _NS)


def _xml_tag(tag):
    return f'{{{_NS}}}{tag}'


class _XLSXWriter:
    """纯 stdlib XLSX 写入器。"""

    def __init__(self):
        self.sheets = {}
        self.col_widths = {}
        self.merges = {}
        self.freezes = {}
        self._strings = []
        self._str_idx = {}

    def _add_str(self, s):
        s = str(s)
        if s not in self._str_idx:
            self._str_idx[s] = len(self._strings)
            self._strings.append(s)
        return self._str_idx[s]

    def add_sheet(self, name, col_widths=None, merges=None, freeze=None):
        name = name[:31]
        self.sheets[name] = []
        if col_widths:
            self.col_widths[name] = col_widths
        if merges:
            self.merges[name] = merges
        if freeze:
            self.freezes[name] = freeze

    def add_row(self, sheet, values):
        self.sheets[sheet].append(values)

    def _col_letter(self, n):
        s = ''
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    def _build_styles_xml(self):
        fonts_el = ET.Element(_xml_tag('fonts'), count='3')
        ET.SubElement(fonts_el, _xml_tag('font'))
        fb = ET.SubElement(fonts_el, _xml_tag('font'))
        ET.SubElement(fb, _xml_tag('b'))
        ET.SubElement(fb, _xml_tag('color'), rgb='FFFFFFFF')
        fb2 = ET.SubElement(fonts_el, _xml_tag('font'))
        ET.SubElement(fb2, _xml_tag('b'))
        fills_el = ET.Element(_xml_tag('fills'), count='5')
        ET.SubElement(fills_el, _xml_tag('fill'))
        ET.SubElement(ET.SubElement(fills_el, _xml_tag('fill')), _xml_tag('patternFill'), patternType='gray125')
        fh = ET.SubElement(fills_el, _xml_tag('fill'))
        ET.SubElement(fh, _xml_tag('patternFill'), patternType='solid').append(
            ET.Element(_xml_tag('fgColor'), rgb='FF4472C4'))
        ft = ET.SubElement(fills_el, _xml_tag('fill'))
        ET.SubElement(ft, _xml_tag('patternFill'), patternType='solid').append(
            ET.Element(_xml_tag('fgColor'), rgb='FFD9E2F3'))
        fg = ET.SubElement(fills_el, _xml_tag('fill'))
        ET.SubElement(fg, _xml_tag('patternFill'), patternType='solid').append(
            ET.Element(_xml_tag('fgColor'), rgb='FFF2F2F2'))
        borders_el = ET.Element(_xml_tag('borders'), count='1')
        ET.SubElement(borders_el, _xml_tag('border'))
        style_xml = ET.Element(_xml_tag('styleSheet'))
        style_xml.append(fonts_el)
        style_xml.append(fills_el)
        style_xml.append(borders_el)
        ET.SubElement(style_xml, _xml_tag('cellStyleXfs'), count='1').append(
            ET.Element(_xml_tag('xf'), numFmtId='0', fontId='0', fillId='0', borderId='0'))
        xfs = ET.SubElement(style_xml, _xml_tag('cellXfs'), count='5')
        ET.SubElement(xfs, _xml_tag('xf'), numFmtId='0', fontId='0', fillId='0', borderId='0', xfId='0')
        ET.SubElement(xfs, _xml_tag('xf'), numFmtId='0', fontId='1', fillId='2', borderId='0', xfId='0', applyFont='1', applyFill='1')
        ET.SubElement(xfs, _xml_tag('xf'), numFmtId='0', fontId='2', fillId='3', borderId='0', xfId='0', applyFont='1', applyFill='1')
        ET.SubElement(xfs, _xml_tag('xf'), numFmtId='0', fontId='2', fillId='0', borderId='0', xfId='0', applyFont='1')
        ET.SubElement(xfs, _xml_tag('xf'), numFmtId='0', fontId='0', fillId='4', borderId='0', xfId='0', applyFill='1')
        return ET.tostring(style_xml, encoding='utf-8', xml_declaration=True)

    def _build_shared_strings_xml(self):
        sst = ET.Element(_xml_tag('sst'), count=str(len(self._strings)),
                         uniqueCount=str(len(self._strings)))
        for s in self._strings:
            si = ET.SubElement(sst, _xml_tag('si'))
            ET.SubElement(si, _xml_tag('t')).text = s
        return ET.tostring(sst, encoding='utf-8', xml_declaration=True)

    def _build_sheet_xml(self, name):
        ws = ET.Element(_xml_tag('worksheet'))
        rows = self.sheets[name]
        if name in self.col_widths:
            cols_el = ET.SubElement(ws, _xml_tag('cols'))
            for letter, width in sorted(self.col_widths[name].items()):
                col_num = 0
                for ch in letter:
                    col_num = col_num * 26 + (ord(ch.upper()) - 64)
                ET.SubElement(cols_el, _xml_tag('col'), min=str(col_num), max=str(col_num),
                              width=str(width), customWidth='1')
        sd = ET.SubElement(ws, _xml_tag('sheetData'))
        for row_idx, row_data in enumerate(rows, 1):
            row_el = ET.SubElement(sd, _xml_tag('row'), r=str(row_idx))
            for col_idx, item in enumerate(row_data, 1):
                val, style = item if isinstance(item, tuple) else (item, 0)
                ref = f'{self._col_letter(col_idx)}{row_idx}'
                if isinstance(val, str):
                    idx = self._add_str(val)
                    v_el = ET.Element(_xml_tag('v'))
                    v_el.text = str(idx)
                    ET.SubElement(row_el, _xml_tag('c'), r=ref, t='s', s=str(style)).append(v_el)
                elif isinstance(val, (int, float)):
                    v_el = ET.Element(_xml_tag('v'))
                    v_el.text = str(int(val))
                    ET.SubElement(row_el, _xml_tag('c'), r=ref, s=str(style)).append(v_el)
        if name in self.merges:
            mc_el = ET.SubElement(ws, _xml_tag('mergeCells'), count=str(len(self.merges[name])))
            for r1, c1, r2, c2 in self.merges[name]:
                ref = f'{self._col_letter(c1)}{r1}:{self._col_letter(c2)}{r2}'
                ET.SubElement(mc_el, _xml_tag('mergeCell'), ref=ref)
        if name in self.freezes:
            fp = self.freezes[name]
            sv = ET.SubElement(ws, _xml_tag('sheetViews'))
            sv_el = ET.SubElement(sv, _xml_tag('sheetView'), tabSelected='1', workbookViewId='0')
            pane_el = ET.SubElement(sv_el, _xml_tag('pane'))
            cl = ''.join(c for c in fp if c.isalpha())
            rn = int(''.join(c for c in fp if c.isdigit()))
            pane_el.set('ySplit', str(rn - 1))
            pane_el.set('topLeftCell', fp)
            pane_el.set('activePane', 'bottomRight')
            pane_el.set('state', 'frozen')
        return ET.tostring(ws, encoding='utf-8', xml_declaration=True)

    def save(self, filepath):
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            ct_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                      '<Default Extension="xml" ContentType="application/xml"/>'
                      '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>')
            for name in list(self.sheets.keys()):
                safe = name.replace(' ', '')
                ct_xml += f'<Override PartName="/xl/worksheets/{safe}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            ct_xml += ('<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                       '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                       '</Types>')
            zf.writestr('[Content_Types].xml', ct_xml)
            zf.writestr('_rels/.rels',
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                        '</Relationships>')
            wb_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                      '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
                      ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>')
            for i, name in enumerate(self.sheets.keys(), 1):
                safe = name.replace(' ', '')
                wb_xml += f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>'
            wb_xml += '</sheets></workbook>'
            zf.writestr('xl/workbook.xml', wb_xml)
            rels_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
            for i, name in enumerate(self.sheets.keys(), 1):
                safe = name.replace(' ', '')
                rels_xml += f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/{safe}.xml"/>'
            rels_xml += ('<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                         '<Relationship Id="rIdStrings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
                         '</Relationships>')
            zf.writestr('xl/_rels/workbook.xml.rels', rels_xml)
            zf.writestr('xl/styles.xml', self._build_styles_xml())
            # 先构建所有 sheet XML（填充 shared strings）
            sheet_xmls = {}
            for name in self.sheets.keys():
                safe = name.replace(' ', '')
                sheet_xmls[safe] = self._build_sheet_xml(name)
            # 再写 shared strings（此时已填充完毕）
            zf.writestr('xl/sharedStrings.xml', self._build_shared_strings_xml())
            # 最后写 sheet XML
            for safe, sxml in sheet_xmls.items():
                zf.writestr(f'xl/worksheets/{safe}.xml', sxml)


HDR_STYLE = 1  # 白字蓝底
TOT_STYLE = 2  # 加粗蓝底


def _write_xlsx_simple(filepath, agent_name, agent_display, filtered_models,
                       today_calls_by_model, date_str):
    wb = _XLSXWriter()
    col_widths = {'A': 22}
    for i in range(2, 9):
        col_widths[wb._col_letter(i)] = 16
    wb.add_sheet(agent_display, col_widths=col_widths)
    headers = ['模型', '输入', '输出', '缓存', '调用', '今日调用', '总计', '总计(含缓存)']
    wb.add_row(agent_display, [(h, HDR_STYLE) for h in headers])
    for pm in filtered_models:
        inp = int(pm.get('input', 0))
        out = int(pm.get('output', 0))
        cache = int(pm.get('cache', 0))
        calls = int(pm.get('calls', 0))
        model = pm.get('model', 'unknown')
        tc = today_calls_by_model.get(model, 0)
        wb.add_row(agent_display, [model, inp, out, cache, calls, tc, inp + out, inp + out + cache])
    if len(filtered_models) > 1:
        ti = int(sum(pm.get('input', 0) for pm in filtered_models))
        to = int(sum(pm.get('output', 0) for pm in filtered_models))
        tc = int(sum(pm.get('cache', 0) for pm in filtered_models))
        tca = int(sum(pm.get('calls', 0) for pm in filtered_models))
        ttoday = sum(today_calls_by_model.values())
        wb.add_row(agent_display, [
            ('合计', TOT_STYLE), (ti, TOT_STYLE), (to, TOT_STYLE),
            (tc, TOT_STYLE), (tca, TOT_STYLE), (ttoday, TOT_STYLE),
            (ti + to, TOT_STYLE), (ti + to + tc, TOT_STYLE)])
    wb.save(filepath)

def _write_xlsx_monthly(filepath, agent_name, agent_display, monthly_data, all_months):
    """单 Agent 年度 XLSX，按月拆分列。"""
    wb = _XLSXWriter()
    month_count = len(all_months)
    all_models = sorted({m for d in monthly_data.values() for m in d})
    col_widths = {'A': 22, 'B': 14}
    for i in range(month_count):
        col_widths[wb._col_letter(3 + i)] = 16
    col_widths[wb._col_letter(3 + month_count)] = 16
    merges = []
    wb.add_sheet(agent_display, col_widths=col_widths, merges=merges, freeze='C2')
    headers = ['Model', 'Metric'] + [f'{m}月' for m in all_months] + ['合计']
    wb.add_row(agent_display, [(h, HDR_STYLE) for h in headers])
    row_num = 2
    for model in all_models:
        ms = row_num
        for metric in _METRIC_ORDER:
            vals = [('' if metric != 'input' else model, 0), (_METRIC_LABELS[metric], 0)]
            tot = 0
            for m_label in all_months:
                md = monthly_data[m_label].get(model, {})
                if metric == 'total':
                    v = md.get('input', 0) + md.get('output', 0)
                elif metric == 'total_with_cache':
                    v = md.get('input', 0) + md.get('output', 0) + md.get('cache', 0)
                else:
                    v = md.get(metric, 0)
                tot += v
                vals.append((int(v), 0))
            vals.append((int(tot), 0))
            wb.add_row(agent_display, vals)
            row_num += 1
        merges.append((ms, 1, row_num - 1, 1))
    gt = row_num
    for metric in _METRIC_ORDER:
        vals = [('' if metric != 'input' else '合计', TOT_STYLE), (_METRIC_LABELS[metric], TOT_STYLE)]
        gt_all = 0
        for m_label in all_months:
            ct = 0
            for model in all_models:
                md = monthly_data[m_label].get(model, {})
                if metric == 'total':
                    ct += md.get('input', 0) + md.get('output', 0)
                elif metric == 'total_with_cache':
                    ct += md.get('input', 0) + md.get('output', 0) + md.get('cache', 0)
                else:
                    ct += md.get(metric, 0)
            gt_all += ct
            vals.append((int(ct), TOT_STYLE))
        vals.append((int(gt_all), TOT_STYLE))
        wb.add_row(agent_display, vals)
        row_num += 1
    merges.append((gt, 1, row_num - 1, 1))
    wb.merges[agent_display] = merges
    wb.save(filepath)


def _write_xlsx_multi_monthly(filepath, agents_monthly, all_months, agent_order):
    """多 Agent 年度 XLSX，全部 Agent 在一个 Sheet。"""
    wb = _XLSXWriter()
    month_count = len(all_months)
    col_widths = {'A': 18, 'B': 22, 'C': 14}
    for i in range(month_count):
        col_widths[wb._col_letter(4 + i)] = 16
    col_widths[wb._col_letter(4 + month_count)] = 16
    merges = []
    wb.add_sheet('年度统计', col_widths=col_widths, merges=merges, freeze='D2')
    headers = ['Agent', 'Model', 'Metric'] + [f'{m}月' for m in all_months] + ['合计']
    wb.add_row('年度统计', [(h, HDR_STYLE) for h in headers])
    all_rows = []
    for agent_name, agent_display, monthly_data in agent_order:
        all_models = sorted({m for d in monthly_data.values() for m in d})
        for model in all_models:
            all_rows.append((agent_name, agent_display, model, monthly_data))
    row_num = 2
    for agent_name, agent_display, model, monthly_data in all_rows:
        ms = row_num
        for metric in _METRIC_ORDER:
            vals = [
                ('' if metric != 'input' else agent_display, 0),
                ('' if metric != 'input' else model, 0),
                (_METRIC_LABELS[metric], 0)]
            tot = 0
            for m_label in all_months:
                md = monthly_data[m_label].get(model, {})
                if metric == 'total':
                    v = md.get('input', 0) + md.get('output', 0)
                elif metric == 'total_with_cache':
                    v = md.get('input', 0) + md.get('output', 0) + md.get('cache', 0)
                else:
                    v = md.get(metric, 0)
                tot += v
                vals.append((int(v), 0))
            vals.append((int(tot), 0))
            wb.add_row('年度统计', vals)
            row_num += 1
        merges.append((ms, 1, row_num - 1, 1))
        merges.append((ms, 2, row_num - 1, 2))
    gt = row_num
    for metric in _METRIC_ORDER:
        vals = [('' if metric != 'input' else '全部总计', TOT_STYLE), ('', TOT_STYLE),
                (_METRIC_LABELS[metric], TOT_STYLE)]
        gt_all = 0
        for m_label in all_months:
            ct = 0
            for _, _, model, monthly_data in all_rows:
                md = monthly_data[m_label].get(model, {})
                if metric == 'total':
                    ct += md.get('input', 0) + md.get('output', 0)
                elif metric == 'total_with_cache':
                    ct += md.get('input', 0) + md.get('output', 0) + md.get('cache', 0)
                else:
                    ct += md.get(metric, 0)
            gt_all += ct
            vals.append((int(ct), TOT_STYLE))
        vals.append((int(gt_all), TOT_STYLE))
        wb.add_row('年度统计', vals)
        row_num += 1
    merges.append((gt, 1, row_num - 1, 1))
    merges.append((gt, 2, row_num - 1, 2))
    wb.merges['年度统计'] = merges
    wb.save(filepath)


def export_interactive(data: AgentData, agent: BaseAgent,
                       from_ts: float = None, to_ts: float = None,
                       is_year: bool = False):
    """交互式导出统计。is_year=True 时按月拆分，导出 XLSX/JSON。"""
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
            print(f"    输入 tokens     {fmt_num(inp):>8}")
            print(f"    输出 tokens     {fmt_num(out):>8}")
            print(f"    缓存 tokens     {fmt_num(cache):>8}")
            print(f"    调用次数        {calls} 次 (今日: {today_calls_by_model.get(m, 0)} 次)")
            print(f"    ─────────────────────────────────────")
            print(f"    总计/+缓存     {fmt_num(total_tok)}/{fmt_num(total_w_cache)}")

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
            print(f"    总计/+缓存     {fmt_num(tt)}/{fmt_num(tt + tc)}")
        print()

        # Step 1: 输入目录
        dir_path = os.getcwd()
        try:
            while True:
                dir_input = input("\n请输入导出目录路径 (回车=当前目录, q=取消): ").strip()
                if not dir_input:
                    break
                if dir_input.lower() == "q":
                    print("已取消导出")
                    return
                p = os.path.expanduser(dir_input)
                if os.path.isdir(p):
                    dir_path = p
                    break
                print(f"⚠️ 目录不存在: {p}, 请重试")
        except EOFError:
            pass

        # Step 2: 选择格式
        print("\n选择导出格式:")
        print("  [1] XLSX（默认）")
        print("  [2] JSON")
        fmt = "xlsx"
        try:
            fmt_choice = input("请选择 (1/2, 回车=1): ").strip().lower()
            if fmt_choice in ("2", "json"):
                fmt = "json"
        except EOFError:
            pass

        # Step 3: 写文件
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        if is_year:
            prefix = f"token-stats_{agent.name()}_yearly"
        else:
            prefix = f"token-stats_{agent.name()}"
        filename = f"{prefix}_{timestamp}.{fmt}"
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
            if is_year and from_ts is not None and to_ts is not None:
                months = _split_months(from_ts, to_ts)
                month_labels = [label for label, _, _ in months]
                monthly_data = {}
                total_months = len(months)
                for idx, (label, m_start, m_end) in enumerate(months, 1):
                    print(f"  ⏳ 正在收集 {label} 数据 ({idx}/{total_months})...", end="\r", flush=True)
                    m_data = agent.collect(from_ts=m_start, to_ts=m_end)
                    monthly_data[label] = {
                        pm.get("model", "unknown"): {
                            "input": pm.get("input", 0), "output": pm.get("output", 0),
                            "cache": pm.get("cache", 0), "calls": pm.get("calls", 0),
                        }
                        for pm in (m_data.per_model or []) if not _skip_model(pm)
                    }
                print(" " * 40, end="\r")  # clear
                _write_xlsx_monthly(filepath, agent.name(), agent.display_name(),
                                    monthly_data, month_labels)
            else:
                _write_xlsx_simple(filepath, agent.name(), agent.display_name(),
                                   filtered_models, today_calls_by_model, date_str)

        print(f"✅ 已导出到: {filepath}")
    except KeyboardInterrupt:
        print()
        print("已取消导出")


def export_multi(results: list[tuple[BaseAgent, AgentData]],
                  is_year: bool = False, from_ts: float = None, to_ts: float = None):
    """导出多个 Agent 的统计（合并输出）。is_year=True 时按月拆分。"""
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
                print(f"      总计/+缓存     {fmt_num(total_tok)}/{fmt_num(total_w_cache)}")

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
                print(f"      总计/+缓存     {fmt_num(tt)}/{fmt_num(tt + tc)}")
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
            print(f"    总计/+缓存     {fmt_num(gtt)}/{fmt_num(gtt + grand_tc)}")

        # Step 1: 输入目录
        dir_path = os.getcwd()
        try:
            while True:
                dir_input = input("\n请输入导出目录路径 (回车=当前目录, q=取消): ").strip()
                if not dir_input:
                    break
                if dir_input.lower() == "q":
                    print("已取消导出")
                    return
                p = os.path.expanduser(dir_input)
                if os.path.isdir(p):
                    dir_path = p
                    break
                print(f"⚠️ 目录不存在: {p}, 请重试")
        except EOFError:
            pass

        # Step 2: 选择格式
        fmt = "xlsx"
        try:
            print("\n选择导出格式:")
            print("  [1] XLSX（默认）")
            print("  [2] JSON")
            fmt_choice = input("请选择 (1/2, 回车=1): ").strip().lower()
            if fmt_choice in ("2", "json"):
                fmt = "json"
        except EOFError:
            pass

        # Step 3: 写文件
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        agent_names = "+".join(agent.name() for agent, _, _, _ in agent_data_list)
        if is_year:
            filename = f"token-stats_{agent_names}_yearly_{timestamp}.{fmt}"
        else:
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
            print(f"  {filepath}")
            print(f"多 Agent 数据已合并导出")
        else:
            if is_year and from_ts is not None and to_ts is not None:
                months = _split_months(from_ts, to_ts)
                month_labels = [label for label, _, _ in months]
                agent_order = []
                for agent, data, today_calls, today_calls_by_model in agent_data_list:
                    agent_models = [pm for pm in (data.per_model or []) if not _skip_model(pm)]
                    if not agent_models:
                        continue
                    monthly_data = {}
                    total_months = len(months)
                    for idx, (label, m_start, m_end) in enumerate(months, 1):
                        print(f"  ⏳ 正在收集 {agent.display_name()} {label} 数据 ({idx}/{total_months})...", end="\r", flush=True)
                        m_data = agent.collect(from_ts=m_start, to_ts=m_end)
                        monthly_data[label] = {
                            pm.get("model", "unknown"): {
                                "input": pm.get("input", 0), "output": pm.get("output", 0),
                                "cache": pm.get("cache", 0), "calls": pm.get("calls", 0),
                            }
                            for pm in (m_data.per_model or []) if not _skip_model(pm)
                        }
                    print(" " * 50, end="\r")
                    agent_order.append((agent.name(), agent.display_name(), monthly_data))
                _write_xlsx_multi_monthly(filepath, agent_order, month_labels, agent_order)
                print(f"  {filepath}")
                print(f"多 Agent 数据已合并导出")
            else:
                # 单 Sheet 合并所有 Agent
                wb = _XLSXWriter()
                col_widths = {'A': 18, 'B': 22}
                for i in range(3, 10):
                    col_widths[wb._col_letter(i)] = 16
                wb.add_sheet('多Agent统计', col_widths=col_widths)
                headers = ['Agent', '模型', '输入', '输出', '缓存', '调用', '今日调用', '总计', '总计(含缓存)']
                wb.add_row('多Agent统计', [(h, HDR_STYLE) for h in headers])
                grand_ti = grand_to = grand_tc = grand_tca = grand_tday = 0
                for agent, data, today_calls, today_calls_by_model in agent_data_list:
                    agent_models = [pm for pm in (data.per_model or []) if not _skip_model(pm)]
                    if not agent_models:
                        continue
                    ti = to = tc = tca = 0
                    for pm in agent_models:
                        inp = pm.get('input', 0)
                        out = pm.get('output', 0)
                        cache = pm.get('cache', 0)
                        calls = pm.get('calls', 0)
                        model = pm.get('model', 'unknown')
                        tc_model = today_calls_by_model.get(model, 0)
                        wb.add_row('多Agent统计', [
                            agent.display_name(), model, int(inp), int(out), int(cache),
                            int(calls), tc_model, int(inp + out), int(inp + out + cache)])
                        ti += inp; to += out; tc += cache; tca += calls
                    if len(agent_models) > 1:
                        wb.add_row('多Agent统计', [
                            ('合计', TOT_STYLE), ('', TOT_STYLE), (int(ti), TOT_STYLE),
                            (int(to), TOT_STYLE), (int(tc), TOT_STYLE), (int(tca), TOT_STYLE),
                            (today_calls, TOT_STYLE), (int(ti + to), TOT_STYLE),
                            (int(ti + to + tc), TOT_STYLE)])
                    grand_ti += ti; grand_to += to; grand_tc += tc; grand_tca += tca; grand_tday += today_calls
                if len(agent_data_list) > 1:
                    gtt = grand_ti + grand_to
                    wb.add_row('多Agent统计', [
                        ('全部总计', TOT_STYLE), ('', TOT_STYLE), (int(grand_ti), TOT_STYLE),
                        (int(grand_to), TOT_STYLE), (int(grand_tc), TOT_STYLE),
                        (int(grand_tca), TOT_STYLE), (grand_tday, TOT_STYLE),
                        (int(gtt), TOT_STYLE), (int(gtt + grand_tc), TOT_STYLE)])
                wb.save(filepath)
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

    print("  ⏳ 正在收集对比数据...", end="\r", flush=True)
    data_a = agent.collect(from_ts=a_start, to_ts=a_end)
    data_b = agent.collect(from_ts=b_start, to_ts=b_end)
    print(" " * 30, end="\r")

    models_a = {pm["model"]: pm for pm in (data_a.per_model or []) if not _skip_model(pm)}
    models_b = {pm["model"]: pm for pm in (data_b.per_model or []) if not _skip_model(pm)}
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
                print(f"  ⏳ 正在收集 {cls.display_name()} 数据...", end="\r", flush=True)
                data = agent.collect(from_ts=from_ts, to_ts=to_ts)
                print(" " * 40, end="\r")
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
    token-stats -v / --version        显示版本号
    token-stats -a <name> --detail    详细模式（同默认）
    token-stats -a <name> --now       当前快照（同默认）

  快速时间段:
    token-stats -a <name> -t / --today     今日统计
    token-stats -a <name> -y / --yesterday 昨日统计
    token-stats -a <name> --week           本周统计（周一起）
    token-stats -a <name> --last-7d        最近 7 天
    token-stats -a <name> -m / --month     本月统计
    token-stats -a <name> --year           本年统计
    token-stats -a <name> --from 2025-01-01 --to 2025-01-31  自定义时间段

  对比:
    token-stats -a <name> --compare --a today --b yesterday
        快捷标签对比
    token-stats -a <name> --compare --a 2025-01-01~2025-01-07 --b 2025-01-08~2025-01-14
        自定义时间段对比
    标签支持: today / yesterday / this-week / last-week / this-month / last-month / this-year / last-year / YYYY-MM-DD / YYYY-MM-DD~YYYY-MM-DD

  导出:
    token-stats -a <name> -e / --export    导出当前统计（交互式选目录和格式）
    token-stats -a <name> -t -e            导出今日统计

  实时监控:
    token-stats -a <name> -w / --watch     实时监控，默认 5 秒刷新 (Ctrl+C 停止)
    token-stats -a <name> -w 10            自定义间隔秒数
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
    parser.add_argument("-v", "--version", action="store_true", help="显示版本号")
    parser.add_argument("-l", "--list-backends", action="store_true", help="列出本机已安装的 Agent")
    parser.add_argument("-a", "--agent", help="直接指定 Agent: hermes/claude-code/codex/openclaw")
    parser.add_argument("-w", "--watch", nargs="?", type=int, const=5, default=None, metavar="秒",
                        help="实时监控模式（默认每 5 秒轮询）")
    parser.add_argument("setup_pos", nargs="?", const=True, help=argparse.SUPPRESS)

    # 时间段
    parser.add_argument("-t", "--today", action="store_true", help="今日统计")
    parser.add_argument("-y", "--yesterday", action="store_true", help="昨日统计")
    parser.add_argument("--week", action="store_true", help="本周统计")
    parser.add_argument("--last-7d", action="store_true", help="最近 7 天统计")
    parser.add_argument("-m", "--month", action="store_true", help="本月统计")
    parser.add_argument("--year", action="store_true", help="本年统计")
    parser.add_argument("--from", dest="from_date", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="结束日期 (YYYY-MM-DD)")

    # 功能
    parser.add_argument("-e", "--export", nargs="?", const=True, default=None, metavar="目录",
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
    elif args.month:
        from_ts, to_ts = parse_time_label("this-month")
    elif args.year:
        from_ts, to_ts = parse_time_label("this-year")

    # ── Helper: collect agent data ──
    def _collect_agent_data(agents_list):
        results = []
        for agent in agents_list:
            try:
                print(f"  ⏳ 正在收集 {agent.display_name()} 数据...", end="\r", flush=True)
                data = agent.collect(from_ts=from_ts, to_ts=to_ts)
                print(" " * 40, end="\r")
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
                export_multi(results, is_year=args.year, from_ts=from_ts, to_ts=to_ts)
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
                export_multi(results, is_year=args.year, from_ts=from_ts, to_ts=to_ts)
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
        agent = show_menu(installed, allow_all=args.watch is None)
        if agent == "all":
            show_all(from_ts=from_ts, to_ts=to_ts)
            return
        if agent is None:
            print("再见 👋")
            return

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
        print("  ⏳ 正在收集数据...", end="\r", flush=True)
        data = agent.collect(from_ts=from_ts, to_ts=to_ts)
        print(" " * 30, end="\r")  # clear progress line
        print()
        print(data.raw)
        print()
    except Exception as e:
        print(f"❌ 获取 {agent.display_name()} 统计失败: {e}")
        return

    # ── --export (导出) ──
    if args.export:
        export_interactive(data, agent, from_ts=from_ts, to_ts=to_ts, is_year=args.year)

    # --detail 在下一步也可能有用，但当前 collect() 已含 per_model 详情
    # detail 主要用于 watch/collect 输出内容更丰富，当前 collect 实现已包含
    # 后续可通过 stats 或 per_model 扩展


if __name__ == "__main__":
    main()
