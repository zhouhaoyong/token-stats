# Changelog

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
