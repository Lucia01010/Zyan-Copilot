# M1 — Excel 与 SQLite 数据 Schema

导入脚本：`scripts/import_excel_to_sqlite.py`

默认数据库：`data/beauty_cs_agent.sqlite3`

运行：

```powershell
python scripts/import_excel_to_sqlite.py --db data/beauty_cs_agent.sqlite3
```

脚本按 sheet 重建目标表，写入 `import_runs`，因此重复运行是幂等的（每个业务表先删除并按当前 workbook 重建）。原始 workbook 不会被写入。

## SQLite 表

所有业务字段和 `_row_number` 使用 `TEXT`/`INTEGER`。所有标识符（会话、订单、工单、消息、物流、商品 SKU、批次号、退款编号）都作为字符串导入；金额和日期保留为规范化文本，后续 service 层按业务需要解析。

| 表 | 主来源 | 关键字段 |
|---|---|---|
| `data_description` | 数据说明 | `column_1` … `column_8` |
| `chat_messages` | 聊天记录 | `conversation_id`, `message_sequence`, `message_id`, `sent_at`, `role`, `buyer_nickname`, `scene_major`, `scene_minor`, `message_text`, `order_number`, `work_order_number` |
| `orders` | 订单 | `order_number`, `conversation_id`, `buyer_nickname`, `product_sku`, `product_name`, `quantity`, `unit_price_yuan`, `paid_amount_yuan`, `order_status`, `ordered_at`, `paid_at`, `shipped_at`, `carrier`, `tracking_number` |
| `replacement_work_orders` | 补发换货工单 | `work_order_number`, `conversation_id`, `order_number`, `work_order_type`, `after_sales_reason`, `sent_product_sku`, `original_tracking_number`, `replacement_tracking_number`, `work_order_status` |
| `offline_payment_work_orders` | 线下打款工单 | `work_order_number`, `conversation_id`, `order_number`, `payment_type`, `refund_issue_type`, `refund_amount_yuan`, `alipay_account`, `transfer_status`, `work_order_status` |
| `logistics_work_orders` | 物流工单 | `work_order_number`, `conversation_id`, `order_number`, `issue_type`, `problem_tracking_number`, `carrier`, `resolution`, `work_order_status` |
| `adverse_reaction_work_orders` | 不良反应工单 | `work_order_number`, `conversation_id`, `order_number`, `reaction_type`, `age`, `skin_type`, `used_product`, `product_batch_number`, `symptom_description`, `stopped_use`, `sought_medical_care`, `task_status` |
| `after_sales_return_work_orders` | 售后退货工单 | `work_order_number`, `conversation_id`, `order_number`, `package_type`, `return_reason`, `return_tracking_number`, `refund_number`, `is_abnormal`, `task_status` |
| `import_runs` | 导入运行记录 | `source_path`, `source_sha256`, `imported_at`, `table_summary_json` |

字段名由中文业务表头映射为稳定英文名；未建立映射的表头使用 `column_N`，避免丢弃源数据。

## 质量约束

- 空行跳过，原始行号写入 `_row_number`。
- 日期按 ISO 文本保存；整数、浮点和 Decimal 使用固定点文本，避免科学计数法。
- 导入前计算 workbook SHA-256，写入 `import_runs`，便于审计。
- `import_runs` 保留每次导入记录；业务表重建不会改动 `data/raw/`。
