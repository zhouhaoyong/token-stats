#!/usr/bin/env python
"""回归测试脚本 — 覆盖 README 80%+ 命令，跨平台（Windows/Linux/macOS）
用法: python test_regression.py
"""

import subprocess
import sys
import os
from pathlib import Path

# 确保 stdout 能处理 UTF-8（Windows GBK 终端写 emoji 会崩）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", errors="replace", closefd=False)

SCRIPT = str(Path(__file__).resolve().parent / "token-stats.py")
OUT = str(Path(__file__).resolve().parent)

def sep(title):
    print(f"\n{'#' * 70}")
    print(f"#  {title}")
    print(f"{'#' * 70}\n")

def run(cmd, timeout=30, stdin=None):
    print(f"$ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    print()
    try:
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, input=stdin,
            encoding="utf-8", errors="replace", env=env
        )
        out = r.stdout + r.stderr
        print(out if out.strip() else "(无输出)")
        if r.returncode != 0:
            print(f"[退出码: {r.returncode}]")
    except subprocess.TimeoutExpired:
        print("(超时)")
    except FileNotFoundError:
        print(f"[错误: 找不到命令 — {cmd[0]}]")
    print()

PY = [sys.executable]

# ══════════════════════════════════════════════════════════════
# 1. 基础信息
# ══════════════════════════════════════════════════════════════
sep("1. 版本信息")
run(PY + [SCRIPT, "--version"])

sep("2. 已安装 Agent 列表")
run(PY + [SCRIPT, "-l"])

# ══════════════════════════════════════════════════════════════
# 2. 单 Agent 快照（默认 / 时间段）
# ══════════════════════════════════════════════════════════════
sep("4. Claude Code 全部历史")
run(PY + [SCRIPT, "-a", "claude-code"])

sep("5. Hermes 全部历史")
run(PY + [SCRIPT, "-a", "hermes"])

sep("6. Claude Code 今日 (-t)")
run(PY + [SCRIPT, "-a", "claude-code", "-t"])

sep("7. Claude Code 昨日 (--yesterday)")
run(PY + [SCRIPT, "-a", "claude-code", "--yesterday"])

sep("8. Claude Code 本周 (--week)")
run(PY + [SCRIPT, "-a", "claude-code", "--week"])

sep("9. Claude Code 最近7天 (--last-7d)")
run(PY + [SCRIPT, "-a", "claude-code", "--last-7d"])

sep("10. Claude Code 本月 (-m)")
run(PY + [SCRIPT, "-a", "claude-code", "-m"])

sep("11. Claude Code 本年 (-y)")
run(PY + [SCRIPT, "-a", "claude-code", "-y"])

sep("12. Claude Code 日期范围 (--from --to)")
run(PY + [SCRIPT, "-a", "claude-code", "--from", "2026-05-20", "--to", "2026-05-24"])

# ══════════════════════════════════════════════════════════════
# 3. --all 模式
# ══════════════════════════════════════════════════════════════
sep("13. 全部 Agent 全部历史")
run(PY + [SCRIPT, "--all"])

sep("14. 全部 Agent 今日 (--all -t)")
run(PY + [SCRIPT, "--all", "-t"])

sep("15. 全部 Agent 本月 (--all -m)")
run(PY + [SCRIPT, "--all", "-m"])

# ══════════════════════════════════════════════════════════════
# 4. 对比模式
# ══════════════════════════════════════════════════════════════
sep("16. Claude Code 对比 today vs yesterday")
run(PY + [SCRIPT, "-a", "claude-code", "--compare", "--a", "today", "--b", "yesterday"])

sep("17. Claude Code 对比 this-week vs last-week")
run(PY + [SCRIPT, "-a", "claude-code", "--compare", "--a", "this-week", "--b", "last-week"])

sep("18. Claude Code 对比 this-month vs last-month")
run(PY + [SCRIPT, "-a", "claude-code", "--compare", "--a", "this-month", "--b", "last-month"])

sep("19. Claude Code 对比日期范围")
run(PY + [SCRIPT, "-a", "claude-code", "--compare",
     "--a", "2026-05-20~2026-05-24", "--b", "2026-05-13~2026-05-17"])

# ══════════════════════════════════════════════════════════════
# 5. 详细模式
# ══════════════════════════════════════════════════════════════
sep("20. Claude Code 详细模式 (--detail)")
run(PY + [SCRIPT, "-a", "claude-code", "--detail"])

# ══════════════════════════════════════════════════════════════
# 6. 实时监控 (20秒)
# ══════════════════════════════════════════════════════════════
sep("21. Claude Code 实时监控 20秒 (-w 5)")
print("(监控中，请等待 20 秒...)\n")
run(PY + [SCRIPT, "-a", "claude-code", "-w", "5"], timeout=22)

# ══════════════════════════════════════════════════════════════
# 7. 导出
# ══════════════════════════════════════════════════════════════
sep("22. 导出 XLSX (Claude Code 本月)")
run(PY + [SCRIPT, "-a", "claude-code", "--month", "-e", OUT])

sep("23. 导出 XLSX (全部 Agent 本年)")
run(PY + [SCRIPT, "--all", "--year", "-e", OUT])

sep("24. 导出 CSV (Claude Code 今日)")
run(PY + [SCRIPT, "-a", "claude-code", "-t", "-e", OUT], stdin="2\n")

sep("25. 导出 JSON (Claude Code 本月)")
run(PY + [SCRIPT, "-a", "claude-code", "--month", "-e", OUT], stdin="3\n")

# ══════════════════════════════════════════════════════════════
# 完成
# ══════════════════════════════════════════════════════════════
sep("回归测试完成 — 导出文件列表")
exported = list(Path(OUT).glob("*.xlsx")) + \
           list(Path(OUT).glob("*.csv")) + \
           list(Path(OUT).glob("*.json"))
if exported:
    for f in exported:
        size = f.stat().st_size
        print(f"  {f.name}  ({size / 1024:.1f} KB)")
else:
    print("  (无导出文件)")

print("\n导出文件已保留在当前目录，请手动检查后删除")
