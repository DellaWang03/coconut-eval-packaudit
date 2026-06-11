# PackAudit

命令行工具，用于核对当天发货 CSV 数据。读取订单文件和扫描文件，按包裹号合并后输出 JSON 审计报告。

## 安装

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## 使用

```bash
packaudit audit \
  --orders orders.csv \
  --scans scans.csv \
  --as-of 2026-06-11 \
  --output report.json
```

### 输入文件格式

**orders.csv** — 必需列：`package_id`, `carrier`, `promised_ship_time`

```csv
package_id,carrier,promised_ship_time
PKG001,SF-Express,2026-06-11 18:00:00
PKG002,YTO,2026-06-11 20:00:00
```

**scans.csv** — 必需列：`package_id`, `scan_time`

```csv
package_id,scan_time
PKG001,2026-06-11 09:00:00
PKG001,2026-06-11 15:00:00
```

### 输出报告

JSON 报告包含：

- `as_of` — 审计基准日期
- `total_orders` — 总订单数
- `delayed_orders` — 延误订单数
- `orders` — 每个包裹的详情（首扫/末扫时间、是否延误、问题列表）
- `carrier_delay_summary` — 按承运商汇总的延误数

### 问题标记

| 标记 | 含义 |
|------|------|
| `missing_scan` | 订单无对应扫描记录 |
| `duplicate_scan` | 同一包裹存在相同时间戳的重复扫描 |

### 错误处理

- 文件不存在：`Error: File not found: xxx`
- 缺少必需列：`Error: Missing required columns in xxx: [...]`
- 日期格式错误：`Error: Bad datetime '...' in ...`
- `--as-of` 格式错误：`Error: Bad date '...'. Expected format: YYYY-MM-DD`

## 测试

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -e ".[dev]" && .venv/bin/python -m pytest -q
```
