     1|#!/usr/bin/env python3
     2|"""
     3|token-stats — 选个 Agent 看它的 token 消耗
     4|
     5|用法:
     6|  token-stats                    交互式菜单：选 Agent → 看统计
     7|  token-stats -b hermes          直接查看 Hermes
     8|  token-stats --watch            交互式菜单 → 实时监控
     9|  token-stats --all              查看本机所有 Agent 的统计
    10|  token-stats -b hermes --now    同默认（显式快照）
    11|
    12|  时间段查询:
    13|  token-stats -b hermes --today
    14|  token-stats -b hermes --yesterday
    15|  token-stats -b hermes --week
    16|  token-stats -b hermes --last-7d
    17|  token-stats -b hermes --from 2025-01-01 --to 2025-01-31
    18|
    19|  导出:
    20|  token-stats -b hermes --export
    21|  token-stats -b hermes --today --export
    22|
    23|  对比:
    24|  token-stats -b hermes --compare --a today --b yesterday
    25|  token-stats -b hermes --compare --a this-week --b last-week
    26|  token-stats -b hermes --compare --a 2025-01-01 --b 2025-01-15
    27|  token-stats -b hermes --compare --a 2025-01-01~2025-01-07 --b 2025-01-08~2025-01-14
    28|
    29|  详细模式:
    30|  token-stats -b hermes --detail
    31|
    32|安装:
    33|  clawhub install agent-usage-stats
    34|  token-stats setup              创建 ~/.local/bin/token-stats
    35|"""
    36|
    37|import argparse
    38|import csv
    39|import json
    40|import os
    41|import re
    42|import signal
    43|import sqlite3
    44|import sys
    45|import threading
    46|import time
    47|from abc import ABC, abstractmethod
    48|from dataclasses import dataclass, field
    49|from datetime import datetime, timedelta
    50|from typing import Optional
    51|
VERSION = "2.0.7"
    53|
    54|# 强制 stdout 行缓冲，使 --watch 模式的输出实时可见
    55|sys.stdout.reconfigure(line_buffering=True)
    56|
    57|
    58|# ═══════════════════════════════════════════════════
    59|#  工具函数
    60|# ═══════════════════════════════════════════════════
    61|
    62|def fmt_num(n: int) -> str:
    63|    if abs(n) < 1000:
    64|        return str(n)
    65|    elif abs(n) < 1_000_000:
    66|        return f"{n/1000:.1f}K"
    67|    else:
    68|        return f"{n/1_000_000:.2f}M"
    69|
    70|
    71|def fmt_pct(pct: float) -> str:
    72|    if pct >= 100:
    73|        return ">100%"
    74|    elif pct >= 90:
    75|        return f"{pct:.1f}% 🚨"
    76|    elif pct >= 60:
    77|        return f"{pct:.1f}% ⚠️"
    78|    else:
    79|        return f"{pct:.1f}% ✅"
    80|
    81|
    82|MODEL_CONTEXT_MAP = {
    83|    "deepseek-v4-flash": 1_048_576,
    84|    "deepseek-v4": 1_048_576,
    85|    "deepseek-chat": 1_048_576,
    86|    "deepseek-reasoner": 1_048_576,
    87|    "deepseek-v3": 131_072,
    88|    "gpt-4o": 131_072,
    89|    "gpt-4o-mini": 131_072,
    90|    "claude-sonnet-4": 204_800,
    91|    "claude-opus-4": 204_800,
    92|    "claude-haiku-3.5": 204_800,
    93|    "gemini-2.5-pro": 1_048_576,
    94|    "gemini-2.0-flash": 1_048_576,
    95|    "qwen3": 131_072,
    96|    "qwen-plus": 131_072,
    97|    "llama-3.1": 131_072,
    98|    "mistral-large": 131_072,
    99|}
   100|
   101|DEFAULT_CONTEXT = 131_072
   102|
   103|
   104|def detect_context(model_name: str) -> int:
   105|    if not model_name:
   106|        return DEFAULT_CONTEXT
   107|    m = model_name.lower().strip()
   108|    if m in MODEL_CONTEXT_MAP:
   109|        return MODEL_CONTEXT_MAP[m]
   110|    for key, val in sorted(MODEL_CONTEXT_MAP.items(), key=lambda x: -len(x[0])):
   111|        if m.startswith(key):
   112|            return val
   113|    return DEFAULT_CONTEXT
   114|
   115|
   116|def parse_date(s: str) -> tuple:
   117|    """Parse 'YYYY-MM-DD' → (start_ts, end_ts)"""
   118|    try:
   119|        dt = datetime.strptime(s.strip(), "%Y-%m-%d")
   120|    except ValueError:
   121|        print(f"❌ 日期格式错误或日期不存在: {s}")
   122|        print("   请使用 YYYY-MM-DD 格式输入有效日期（例如 2025-06-15）")
   123|        sys.exit(1)
   124|    now = datetime.now()
   125|    # 未来日期 → 自动截断到当前时间
   126|    if dt > now:
   127|        dt = now
   128|        print(f"⚠️ 日期 {s} 在未来，已自动截断到当前时间")
   129|    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
   130|    end = dt.replace(hour=23, minute=59, second=59, microsecond=0)
   131|    return start.timestamp(), end.timestamp()
   132|
   133|
   134|def parse_time_label(label: str) -> tuple:
   135|    """Parse a time label → (start_ts, end_ts).
   136|
   137|    Supports:
   138|      today, yesterday, this-week / week, last-week, last-7d
   139|      YYYY-MM-DD (single day)
   140|      YYYY-MM-DD~YYYY-MM-DD (date range)
   141|    """
   142|    s = label.strip().lower()
   143|    now = datetime.now()
   144|
   145|    if s == "today":
   146|        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
   147|        return start.timestamp(), now.timestamp()
   148|
   149|    if s == "yesterday":
   150|        d = now - timedelta(days=1)
   151|        start = d.replace(hour=0, minute=0, second=0, microsecond=0)
   152|        end = d.replace(hour=23, minute=59, second=59, microsecond=0)
   153|        return start.timestamp(), end.timestamp()
   154|
   155|    if s in ("this-week", "week"):
   156|        monday = now - timedelta(days=now.weekday())
   157|        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
   158|        return start.timestamp(), now.timestamp()
   159|
   160|    if s == "last-week":
   161|        monday = now - timedelta(days=now.weekday() + 7)
   162|        sunday = monday + timedelta(days=6)
   163|        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
   164|        end = sunday.replace(hour=23, minute=59, second=59, microsecond=0)
   165|        return start.timestamp(), end.timestamp()
   166|
   167|    if s == "last-7d":
   168|        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
   169|        return start.timestamp(), now.timestamp()
   170|
   171|    # Date range: YYYY-MM-DD~YYYY-MM-DD
   172|    if "~" in s:
   173|        parts = s.split("~", 1)
   174|        start_ts, _ = parse_date(parts[0])
   175|        _, end_ts = parse_date(parts[1])
   176|        return start_ts, end_ts
   177|
   178|    # Single date
   179|    return parse_date(s)
   180|
   181|
   182|def format_model_line(model_name: str, inp: int, out: int, cache: int, calls: int,
   183|                      context_window: int = None, session_count: int = None,
   184|                      extra: str = None) -> str:
   185|    """单行模型输出格式。若全为 0 则返回空字符串。"""
   186|    if inp == 0 and out == 0 and cache == 0 and calls == 0:
   187|        return ""
   188|
   189|    parts = []
   190|    total = inp + out
   191|    if context_window:
   192|        pct = round(total / context_window * 100, 1) if context_window else 0
   193|        parts.append(f"上下文 {fmt_num(total)}/{fmt_num(context_window)} ({fmt_pct(pct)})")
   194|    if inp > 0 or out > 0 or total > 0:
   195|        if not context_window:
   196|            parts.append(f"总计 {fmt_num(total)}")
   197|        parts.append(f"输入 {fmt_num(inp)}")
   198|        parts.append(f"输出 {fmt_num(out)}")
   199|    if cache > 0:
   200|        parts.append(f"缓存 {fmt_num(cache)}")
   201|    if calls > 0 and (not session_count or session_count != calls):
   202|        parts.append(f"调用 {calls} 次")
   203|    elif calls > 0 and session_count == calls and total == 0:
   204|        # 无 token 数据时，不重复显示 "调用 N 次" 和 "N 轮会话"
   205|        pass
   206|    elif calls > 0:
   207|        parts.append(f"调用 {calls} 次")
   208|    if session_count:
   209|        parts.append(f"{session_count} 轮会话")
   210|    if extra:
   211|        parts.append(extra)
   212|    if not parts:
   213|        parts.append("无数据")
   214|    return f"  {model_name} | {' | '.join(parts)}"
   215|
   216|
   217|# ═══════════════════════════════════════════════════
   218|#  Agent 基类与数据模型
   219|# ═══════════════════════════════════════════════════
   220|
   221|@dataclass
   222|class AgentData:
   223|    """单个 Agent 的统计数据"""
   224|    name: str
   225|    display_name: str
   226|    stats: dict
   227|    raw: str
   228|    per_model: list = None  # [{"model": ..., "input": N, "output": N, "calls": N, "cache": N}, ...]
   229|
   230|
   231|class BaseAgent(ABC):
   232|    """Agent 检测器基类"""
   233|
   234|    @staticmethod
   235|    @abstractmethod
   236|    def name() -> str: ...
   237|
   238|    @staticmethod
   239|    @abstractmethod
   240|    def display_name() -> str: ...
   241|
   242|    @staticmethod
   243|    @abstractmethod
   244|    def detect() -> bool: ...
   245|
   246|    @abstractmethod
   247|    def collect(self, *, from_ts: float = None, to_ts: float = None) -> AgentData: ...
   248|
   249|    def watch(self, interval: int = 5) -> None:
   250|        """实时监控模式"""
   251|        stop_event = threading.Event()
   252|
   253|        def _on_signal(sig, frame):
   254|            stop_event.set()
   255|
   256|        signal.signal(signal.SIGINT, _on_signal)
   257|        signal.signal(signal.SIGTERM, _on_signal)
   258|
   259|        def _interruptible_sleep(seconds: float) -> bool:
   260|            """中断式睡眠，返回 False 表示被中断"""
   261|            return not stop_event.wait(timeout=seconds)
   262|
   263|        print(f"\n📡 实时监控 [{self.display_name()}] — 每 {interval} 秒刷新 (Ctrl+C 停止)\n")
   264|
   265|        # ── 首次基线 ──
   266|        data_first = self.collect()
   267|        bl_models = {}
   268|        if data_first.per_model:
   269|            for pm in data_first.per_model:
   270|                bl_models[pm["model"]] = {
   271|                    "input": pm.get("input", 0),
   272|                    "output": pm.get("output", 0),
   273|                    "calls": pm.get("calls", 0),
   274|                    "cache": pm.get("cache", 0),
   275|                }
   276|        else:
   277|            m = data_first.stats.get("model", "?")
   278|            bl_models[m] = {
   279|                "input": data_first.stats.get("input_tokens", 0),
   280|                "output": data_first.stats.get("output_tokens", 0),
   281|                "calls": data_first.stats.get("api_calls", 0),
   282|                "cache": data_first.stats.get("cache_read", 0),
   283|            }
   284|
   285|        # ── 初始状态（单行格式） ──
   286|        print("初始状态:")
   287|        for mn, mv in bl_models.items():
   288|            cw = detect_context(mn)
   289|            line = format_model_line(mn, mv["input"], mv["output"],
   290|                                     mv.get("cache", 0), mv.get("calls", 0),
   291|                                     context_window=cw)
   292|            if line:
   293|                print(line)
   294|        print()
   295|
   296|        # ── 监控循环：每 tick 打印完整当前状态 ──
   297|        prev_models = dict(bl_models)
   298|        while not stop_event.is_set():
   299|            tick_start = time.monotonic()
   300|            if not _interruptible_sleep(interval):
   301|                break
   302|            if stop_event.is_set():
   303|                break
   304|            try:
   305|                data = self.collect()
   306|            except Exception as e:
   307|                print(f"  ⚠️ {e}")
   308|                continue
   309|
   310|            now_models = {}
   311|            if data.per_model:
   312|                for pm in data.per_model:
   313|                    now_models[pm["model"]] = {
   314|                        "input": pm.get("input", 0),
   315|                        "output": pm.get("output", 0),
   316|                        "calls": pm.get("calls", 0),
   317|                        "cache": pm.get("cache", 0),
   318|                    }
   319|            else:
   320|                m = data.stats.get("model", "?")
   321|                now_models[m] = {
   322|                    "input": data.stats.get("input_tokens", 0),
   323|                    "output": data.stats.get("output_tokens", 0),
   324|                    "calls": data.stats.get("api_calls", 0),
   325|                    "cache": data.stats.get("cache_read", 0),
   326|                }
   327|
   328|            # 计算增量 & 更新累计
   329|            ts = datetime.now().strftime("%H:%M:%S")
   330|            changed_models = []
   331|            total_delta_tok = 0
   332|            total_delta_calls = 0
   333|            for mn, mv in now_models.items():
   334|                prev = prev_models.get(mn, {"input": 0, "output": 0, "calls": 0, "cache": 0})
   335|                d_in = mv["input"] - prev["input"]
   336|                d_out = mv["output"] - prev["output"]
   337|                d_calls = mv["calls"] - prev["calls"]
   338|                d_cache = mv["cache"] - prev["cache"]
   339|                d_tok = d_in + d_out
   340|                if d_tok != 0 or d_calls != 0 or d_cache != 0:
   341|                    changed_models.append((mn, d_in, d_out, d_tok, d_calls, d_cache))
   342|                    total_delta_tok += d_tok
   343|                    total_delta_calls += d_calls
   344|                # 记录新出现的模型到 bl_models
   345|                if mn not in bl_models:
   346|                    bl_models[mn] = mv
   347|
   348|            # 每 tick 打印当前完整状态
   349|            print(f"── [{ts}] ──")
   350|            for mn, mv in now_models.items():
   351|                cw = detect_context(mn)
   352|                line = format_model_line(mn, mv["input"], mv["output"],
   353|                                         mv.get("cache", 0), mv.get("calls", 0),
   354|                                         context_window=cw)
   355|                if line:
   356|                    print(line)
   357|                # 如果有增量，追加一行显示变化
   358|                for cm, d_in, d_out, d_tok, d_calls, d_cache in changed_models:
   359|                    if cm == mn:
   360|                        parts = []
   361|                        if d_tok:
   362|                            prefix = "+" if d_tok > 0 else ""
   363|                            parts.append(f"{prefix}{fmt_num(d_tok)} tokens")
   364|                        if d_in:
   365|                            prefix = "+" if d_in > 0 else ""
   366|                            parts.append(f"{prefix}{fmt_num(d_in)} 输入")
   367|                        if d_out:
   368|                            prefix = "+" if d_out > 0 else ""
   369|                            parts.append(f"{prefix}{fmt_num(d_out)} 输出")
   370|                        if d_cache:
   371|                            prefix = "+" if d_cache > 0 else ""
   372|                            parts.append(f"{prefix}{fmt_num(d_cache)} 缓存")
   373|                        if d_calls:
   374|                            prefix = "+" if d_calls > 0 else ""
   375|                            parts.append(f"{prefix}{d_calls} 调用")
   376|                        if parts:
   377|                            print(f"    Δ {' · '.join(parts)}")
   378|
   379|            # 更新 prev_models
   380|            prev_models = dict(now_models)
   381|
   382|            # 精确间隔补偿
   383|            elapsed = time.monotonic() - tick_start
   384|            if elapsed < interval and not stop_event.is_set():
   385|                _interruptible_sleep(interval - elapsed)
   386|
   387|        # ── 停止汇总：从末态减初态计算总变化 ──
   388|        sep_w = 60
   389|        print()
   390|        print("━" * sep_w)
   391|        print("  📊 本次监控汇总")
   392|        print("━" * sep_w)
   393|
   394|        # 计算累计变化：prev_models（最新） - bl_models（初始基线）
   395|        final_deltas = {}
   396|        for mn, mv in prev_models.items():
   397|            bl = bl_models.get(mn, {"input": 0, "output": 0, "calls": 0, "cache": 0})
   398|            d_in = mv["input"] - bl["input"]
   399|            d_out = mv["output"] - bl["output"]
   400|            d_calls = mv["calls"] - bl["calls"]
   401|            d_cache = mv["cache"] - bl["cache"]
   402|            if d_in != 0 or d_out != 0 or d_calls != 0 or d_cache != 0:
   403|                final_deltas[mn] = {"input": d_in, "output": d_out, "calls": d_calls, "cache": d_cache}
   404|
   405|        if final_deltas:
   406|            max_model_len = max(len(mn) for mn in final_deltas)
   407|            model_col = max(max_model_len, 8)
   408|            hdr = f"  {'模型':<{model_col}} {'增量 tokens':>12} {'调用':>6} {'输入':>10} {'输出':>10} {'缓存':>10} {'占用':>8}"
   409|            print(hdr)
   410|            print("  " + "─" * (model_col + 12 + 6 + 10 + 10 + 10 + 8 + 1))
   411|            total_tok = 0
   412|            total_calls = 0
   413|            for mn, cd in sorted(final_deltas.items()):
   414|                d_tok = cd["input"] + cd["output"]
   415|                pct = ""
   416|                cw = detect_context(mn)
   417|                if cw:
   418|                    pct = fmt_pct(round(d_tok / cw * 100, 1))
   419|                print(f"  {mn:<{model_col}} {fmt_num(d_tok):>12} {cd['calls']:>6} "
   420|                      f"{fmt_num(cd['input']):>10} {fmt_num(cd['output']):>10} "
   421|                      f"{fmt_num(cd['cache']):>10} {pct:>8}")
   422|                total_tok += d_tok
   423|                total_calls += cd["calls"]
   424|            print("━" * sep_w)
   425|            print(f"  总计: {fmt_num(total_tok)} tokens, {total_calls} 次调用")
   426|        else:
   427|            print("  监控期间没有检测到变化")
   428|        print("👋 监控已停止")
   429|
   430|
   431|# ═══════════════════════════════════════════════════
   432|#  Hermes
   433|# ═══════════════════════════════════════════════════
   434|
   435|HERMES_DB = os.path.expanduser("~/.hermes/state.db")
   436|
   437|
   438|class HermesAgent(BaseAgent):
   439|    @staticmethod
   440|    def name() -> str:
   441|        return "hermes"
   442|
   443|    @staticmethod
   444|    def display_name() -> str:
   445|        return "Hermes"
   446|
   447|    @staticmethod
   448|    def detect() -> bool:
   449|        return os.path.exists(HERMES_DB)
   450|
   451|    def collect(self, *, from_ts: float = None, to_ts: float = None) -> AgentData:
   452|        conn = sqlite3.connect(HERMES_DB, timeout=5)
   453|        conn.row_factory = sqlite3.Row
   454|
   455|        if from_ts is not None or to_ts is not None:
   456|            # ── 时间段统计 ──
   457|            where = []
   458|            params = []
   459|            if from_ts is not None:
   460|                where.append("started_at >= ?")
   461|                params.append(from_ts)
   462|            if to_ts is not None:
   463|                where.append("started_at <= ?")
   464|                params.append(to_ts)
   465|            clause = " AND ".join(where)
   466|
   467|            cur = conn.execute(
   468|                f"SELECT model, SUM(input_tokens) as inp, SUM(output_tokens) as out, "
   469|                f"SUM(cache_read_tokens) as cache, SUM(api_call_count) as calls, "
   470|                f"SUM(tool_call_count) as tools, COUNT(*) as cnt "
   471|                f"FROM sessions WHERE {clause} GROUP BY model",
   472|                params
   473|            )
   474|            rows = cur.fetchall()
   475|            conn.close()
   476|
   477|            if not rows:
   478|                return AgentData(
   479|                    name="hermes", display_name="Hermes",
   480|                    stats={}, raw="Hermes: 该时间段内无会话记录"
   481|                )
   482|
   483|            total_inp = sum(r["inp"] or 0 for r in rows)
   484|            total_out = sum(r["out"] or 0 for r in rows)
   485|            total_cache = sum(r["cache"] or 0 for r in rows)
   486|            total_calls = sum(r["calls"] or 0 for r in rows)
   487|            total_sessions = sum(r["cnt"] or 0 for r in rows)
   488|
   489|            per_model_list = []
   490|            raw_lines = ["📊 Hermes"]
   491|            for r in rows:
   492|                m = r["model"] or "unknown"
   493|                inp = r["inp"] or 0
   494|                out = r["out"] or 0
   495|                cache = r["cache"] or 0
   496|                calls = r["calls"] or 0
   497|                cnt = r["cnt"] or 0
   498|                per_model_list.append({"model": m, "input": inp, "output": out,
   499|                                        "calls": calls, "cache": cache})
   500|                line = format_model_line(m, inp, out, cache, calls, session_count=cnt)
   501|