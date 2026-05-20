# Changelog

## v2.5.3 (2026-05-20)

### 修复
- **Windows WSL2 数据收集极慢**：Hermes/CodeX 数据库位于 WSL UNC 路径时，`sqlite3.connect(timeout=10)` 被 WSL 文件系统桥放大到 ~30 秒。修复后检测 `//wsl.` 前缀直接走 `wsl.exe` 内部查询（174ms），提速 164 倍
- **CodeX WSL 支持**：新增 `_codex_collect_via_wsl()`，与 Hermes 相同的 WSL 直通机制
- **通用 WSL 检测**：新增 `_is_wsl_unc()` 工具函数，统一判断 WSL UNC 路径

## v2.5.2 (2026-05-20)

### 修复
- **跨平台 setup/update/uninstall 健壮性**：
  - Shell 检测从硬编码（mac→zsh, linux→bash）改为读取 `$SHELL` 环境变量，支持 zsh/bash/fish
  - Fish shell 使用 `fish_add_path` 而非无效的 `export PATH=`
  - Windows PATH 注册表操作加入 `os.path.normpath` 标准化 + 大小写不敏感比较
  - `_remove_from_path_unix` 模式匹配统一，消除重复代码
  - `token-stats update` 用 `shutil.which` 定位 clawhub（修复 Windows 找不到 clawhub.cmd）

## v2.5.1 (2026-05-20)

### 修复
- **`token-stats update` 路径错误**：`--workdir` 从硬编码 `~` 改为脚本实际所在目录，修复不同安装方式下更新到错误路径导致版本号不变的问题
- **update 后刷新 wrapper**：`clawhub update` 成功后自动重写 `~/.local/bin/token-stats`，确保 wrapper 指向正确路径

## v2.5.0 (2026-05-20)

### 修复
- **Windows XLSX 导出为空**：中文 sheet 名（年度统计/多Agent统计）在 ZIP 内产生 UTF-8 路径，Windows 无法识别。改为 ASCII sheet 名（YearlyStats/MultiAgent）
- **总计/+缓存 列显示错误**：缓存为 0 时第二值（含缓存总计）错误显示为 0，统一修正为 `total + cache`（17 处代码路径）
- **对比模式列对齐**：表头覆盖首行数据导致模型名丢失 + 列宽不一致。重写为表头与数据统一 `_align_rows` 对齐
- **对比模式模型分隔**：不同模型之间增加 `·` 分隔线，提高可读性
- **`_align_rows` 最后一列**：最后一列现在也参与填充，所有 `|` 分隔符垂直对齐
- **年度导出重复收集**：月度数据收集前移至格式选择提示之前；单 Agent 年度导出跳过初始全量收集
- **年度导出 data=None 崩溃**：移除 `export_interactive` 中重复的 `filtered_models` 赋值（覆盖月度汇总结果）

### 变更
- **导出空行移除**：XLSX/CSV 导出中 Agent 合计行和全部总计行前的空行分隔符已全部移除

## v2.4.7 (2026-05-20)

### 新增
- **watch 停止汇总增强**：显示监控时长 + 采集轮数

### 修复
- **年度导出 Agent 合计行 Model 列**：补充「合计」标签并正确合并单元格

## v2.4.6 (2026-05-20)

### 新增
- **对比模式重构**：按模型×指标完整对比（入/出/缓/总计/总计含缓存/调用）6 维度
- **`token-stats update`**：自更新指令，固定 workdir 为 ~ 并跳过二次确认

### 修复
- 单模型 Agent 导出不展示重复合计行，仅多模型时展示
- 导出合计行前加空行分隔

### 变更
- `-y` 短参数从 `--yesterday` 改为 `--year`

## v2.4.5 (2026-05-20)

### 修复
- unknown 零数据模型过滤
- Claude Code watch 缓存修复（主 collect 总是缓存）

## v2.4.4 (2026-05-20)

### 修复
- **unknown 模型未过滤**：`_build_aligned_raw` 增加 `_skip_model` 过滤，零数据模型不再显示
- **导出合计行无分隔**：所有 XLSX/CSV 导出在 Agent 合计 + 全部总计前加空行
- **CC watch 缓存再次修复**：磁盘重读后总是缓存消息，今日采集复用不再重复读盘

## v2.4.3 (2026-05-20)

### 修复
- **Claude Code 缓存导致 watch 模式失效**：缓存仅在带时间筛选时启用，无参 collect 始终重读磁盘
- **watch 刷新间隔不准**：循环改为先 collect 再 sleep，实际间隔从 ~10s 修正为 ~5s
- **控制台输出列不对齐**：新增 `_build_aligned_raw` 统一列对齐，全部 Agent 输出一致
- **缺少 Agent 合计行**：多模型时自动追加合计行（入/出/缓/总计/调用）
- **`--all` / 多 Agent 缺少 Grand Total**：末尾显示全部 Agent 总计

### 变更
- **`-y` → `--year`**：短参数从 `--yesterday` 改为 `--year`，`--yesterday` 仅保留长参数
- **导出格式顺序**：`[1] XLSX` / `[2] CSV` / `[3] JSON`
- **导出格式统一**：单/多 Agent 导出均含 Agent 名称列 + 合并单元格 + 单独合计 + 总合计
- `-e /path` 直接使用目录，跳过交互式提示
- watch 分割线加长到 60 列

### 新增
- **CSV 导出**：简单/年度 × 单/多 Agent 全覆盖
- **`token-stats update`**：自更新指令，调用 `clawhub update agent-usage-stats`

## v2.4.2 (2026-05-20)

### 修复
- ClaudeCodeAgent 重复 collect() 不再重读磁盘（消息缓存）
- 移除导出函数冗余的 today_calls 全量收集

### 新增
- CSV 导出格式，菜单顺序 XLSX/CSV/JSON

## v2.4.1 (2026-05-19)

### 变更
- **统一输出风格**：全部输出（快照/增量/今日/累计/导出）均包含独立 `缓` 列 + `总计/+缓存` 合并列
- **多 Agent 导出合并**：单 Sheet 单 XLSX 文件，含 Agent 小计 + 全部总计
- **上下文 Agent 优化**：Hermes/OpenClaw 保留上下文进度条 + 统一融入缓存列

### 修复
- XLSX 导出数据为空（ElementTree text 属性 vs 文本内容 + shared strings 构建顺序）
- CodeX/Hermes SQLite 连接超时（增加 5s/10s timeout 防 hang）
- watch 今日合计列统一对齐

## v2.4.0 (2026-05-19)

### 新增
- **短参数支持**：`-t` (--today), `-y` (--yesterday), `-m` (--month), `-w` (--watch), `-e` (--export), `-v` (--version), `-l` (--list-backends)
- **--month / --year 快捷参数**：直接查看本月/本年统计，无需手动指定 --from/--to
- **--year 月度拆分导出**：年度导出时按月分列展示（1~12月），每月独立统计 + 总计行
- **XLSX 导出**：纯标准库实现，零外部依赖。格式选择 [1] XLSX [2] JSON
- **总计(含缓存)**：新增含缓存的总计指标，区分有无缓存的两类总量
- **数据计算进度提示**：慢速操作（收集数据、对比、月度拆分）时显示进度信息
- **管道/脚本模式**：导出交互支持 EOF 保护，回车使用默认值
- **CHANGELOG.md**：版本更新记录文档

### 变更
- `总计` 和 `缓存` 合并显示为 `总计/+缓存 X/Y`
- 导出格式从 CSV 改为 XLSX（JSON 保留为选项 2）
- 帮助文本更新，展示所有短参数

### 修复
- WSL fallback 异常返回类型修复（元组 → None）
- run_compare 增加 _skip_model 过滤
- export_multi 预过滤空数据 Agent
- parse_time_label 支持 month/year 短别名
- label_to_display 支持 month/year 标签

---

## v2.3.8 (2026-05-18)

- watch 模式列对齐 + 数值精度优化

## v2.3.7 (2026-05-17)

- watch 样式升级：进度条+颜色+虚线框+今日合计

## v2.3.6

- -b→-a/--agent 语义化 + 统计原理说明

## v2.3.5

- 时间过滤修复 + 监控增量增强
