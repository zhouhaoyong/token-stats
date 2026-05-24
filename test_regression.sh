#!/bin/bash
# 回归测试脚本 — 覆盖 README 80%+ 命令
# 用法: bash test_regression.sh

SCRIPT="$(cd "$(dirname "$0")" && pwd)/token-stats.py"
OUT="$(cd "$(dirname "$0")" && pwd)"

sep() {
    echo ""
    echo "######################################################################"
    echo "#  $1"
    echo "######################################################################"
    echo ""
}

run() {
    echo "\$ $1"
    echo ""
    eval "$1" 2>&1 || echo "[退出码: $?]"
    echo ""
}

# ══════════════════════════════════════════════════════════════
# 1. 基础信息
# ══════════════════════════════════════════════════════════════
sep "1. 版本信息"
run "python3 $SCRIPT --version"

sep "2. 已安装 Agent 列表"
run "python3 $SCRIPT -l"

sep "3. 模型价格列表"
run "python3 $SCRIPT --list-prices"

# ══════════════════════════════════════════════════════════════
# 2. 单 Agent 快照（默认 / 时间段）
# ══════════════════════════════════════════════════════════════
sep "4. Claude Code 全部历史"
run "python3 $SCRIPT -a claude-code"

sep "5. Hermes 全部历史"
run "python3 $SCRIPT -a hermes"

sep "6. Claude Code 今日 (-t)"
run "python3 $SCRIPT -a claude-code -t"

sep "7. Claude Code 昨日 (--yesterday)"
run "python3 $SCRIPT -a claude-code --yesterday"

sep "8. Claude Code 本周 (--week)"
run "python3 $SCRIPT -a claude-code --week"

sep "9. Claude Code 最近7天 (--last-7d)"
run "python3 $SCRIPT -a claude-code --last-7d"

sep "10. Claude Code 本月 (-m)"
run "python3 $SCRIPT -a claude-code -m"

sep "11. Claude Code 本年 (-y)"
run "python3 $SCRIPT -a claude-code -y"

sep "12. Claude Code 日期范围 (--from --to)"
run "python3 $SCRIPT -a claude-code --from 2026-05-20 --to 2026-05-24"

# ══════════════════════════════════════════════════════════════
# 3. --all 模式
# ══════════════════════════════════════════════════════════════
sep "13. 全部 Agent 全部历史"
run "python3 $SCRIPT --all"

sep "14. 全部 Agent 今日 (--all -t)"
run "python3 $SCRIPT --all -t"

sep "15. 全部 Agent 本月 (--all -m)"
run "python3 $SCRIPT --all -m"

# ══════════════════════════════════════════════════════════════
# 4. 对比模式
# ══════════════════════════════════════════════════════════════
sep "16. Claude Code 对比 today vs yesterday"
run "python3 $SCRIPT -a claude-code --compare --a today --b yesterday"

sep "17. Claude Code 对比 this-week vs last-week"
run "python3 $SCRIPT -a claude-code --compare --a this-week --b last-week"

sep "18. Claude Code 对比 this-month vs last-month"
run "python3 $SCRIPT -a claude-code --compare --a this-month --b last-month"

sep "19. Claude Code 对比日期范围"
run "python3 $SCRIPT -a claude-code --compare --a 2026-05-20~2026-05-24 --b 2026-05-13~2026-05-17"

# ══════════════════════════════════════════════════════════════
# 5. 详细模式
# ══════════════════════════════════════════════════════════════
sep "20. Claude Code 详细模式 (--detail)"
run "python3 $SCRIPT -a claude-code --detail"

# ══════════════════════════════════════════════════════════════
# 6. 实时监控 (20秒)
# ══════════════════════════════════════════════════════════════
sep "21. Claude Code 实时监控 20秒 (-w 5)"
echo "(监控中，请等待 20 秒...)"
echo ""
timeout 22 python3 "$SCRIPT" -a claude-code -w 5 2>&1 || true
echo ""

# ══════════════════════════════════════════════════════════════
# 7. 导出
# ══════════════════════════════════════════════════════════════
sep "22. 导出 XLSX (Claude Code 本月)"
run "python3 $SCRIPT -a claude-code --month -e $OUT"

sep "23. 导出 XLSX (全部 Agent 本年)"
run "python3 $SCRIPT --all --year -e $OUT"

sep "24. 导出 CSV (Claude Code 今日)"
echo "2" | python3 "$SCRIPT" -a claude-code -t -e "$OUT" 2>&1 || true
echo ""

sep "25. 导出 JSON (Claude Code 本月)"
echo "3" | python3 "$SCRIPT" -a claude-code --month -e "$OUT" 2>&1 || true
echo ""

# ══════════════════════════════════════════════════════════════
# 完成
# ══════════════════════════════════════════════════════════════
sep "回归测试完成 — 导出文件列表"
ls -lh "$OUT"/*.xlsx "$OUT"/*.csv "$OUT"/*.json 2>/dev/null || echo "(无导出文件)"

echo ""
echo "导出文件已保留在当前目录，请手动检查后删除"
