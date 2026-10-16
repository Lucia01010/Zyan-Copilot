# 数据上下文明细（M12 Context Engine）

本文件盘点 Context Engine 可使用的全部数据面。所有内容来自真实赛题 SQLite（`data/beauty_cs_agent.sqlite3`），表与字段均以 `PRAGMA table_info` 实测为准；不存在独立的 customers 表，客户维度由 `buyer_nickname` 在各业务表中承载。

## 客户维度（customers，逻辑实体）

客户不是独立表，由以下字段聚合而成：

| 字段 | 来源表 | 业务含义 |
|------|--------|----------|
| buyer_nickname | chat_messages / orders / 五类工单表 | 买家昵称（脱敏，如"方b**"），客户唯一标识 |
| 会话数 | chat_messages 按 conversation_id 去重统计 | 该客户历史进线次数 |
| 订单数 | orders 按 buyer_nickname 统计 | 该客户关联订单量 |
| 工单数 | 五类工单表按 buyer_nickname 统计 | 该客户售后服务体量 |

## 会话（conversations → chat_messages，998 行）

| 字段 | 来源表 | 业务含义 |
|------|--------|----------|
| conversation_id | chat_messages | 会话编号（如 S00082），会话隔离边界 |
| message_sequence | chat_messages | 会话内消息序号（文本数字，需 CAST 排序） |
| message_id | chat_messages | 消息唯一编号 |
| sent_at | chat_messages | 发送时间（文本时间戳） |
| role | chat_messages | 发送角色（买家/客服） |
| buyer_nickname | chat_messages | 该消息归属客户 |
| sender / store | chat_messages | 发送账号 / 店铺 |
| scene_major / scene_minor | chat_messages | 会话场景大类/细类 |
| message_text / chat_content | chat_messages | 消息正文 |
| content_type / category / image_path | chat_messages | 内容类型、消息分类、图片路径 |
| order_number / work_order_number | chat_messages | 消息中关联的订单号/工单号 |

## 订单（orders，113 行）

| 字段 | 来源表 | 业务含义 |
|------|--------|----------|
| order_number | orders | 订单号（精确匹配键） |
| conversation_id / buyer_nickname / store | orders | 关联会话、客户、店铺 |
| product_sku / product_name / quantity | orders | 商品 SKU、名称、数量 |
| unit_price_yuan / paid_amount_yuan | orders | 单价、实付金额（元，文本） |
| order_status | orders | 订单状态 |
| ordered_at / paid_at / shipped_at | orders | 下单/付款/发货时间 |
| carrier / tracking_number | orders | 承运商、物流单号 |
| shipping_province / shipping_city | orders | 收货省市 |
| gift / buyer_note | orders | 赠品、买家备注 |

## 工单（tickets → 五类工单表）

公共字段：`work_order_number`（工单号）、`conversation_id`、`order_number`、`buyer_nickname`、`store`、`handler`（处理人）、`created_at`、`completed_at`。

| 来源表 | 行数 | 特有字段 | 业务含义 |
|--------|------|----------|----------|
| adverse_reaction_work_orders | 10 | reaction_type、age、skin_type、used_product、product_batch_number、affected_area、symptom_description、onset_after_use、stopped_use、sought_medical_care、task_status | 不良反应登记：症状、部位、停用/就医情况 |
| after_sales_return_work_orders | 18 | package_type、return_reason、return_tracking_number、carrier、refund_number、receipt_recommendation、is_abnormal、task_status | 退货退款：退货原因、退货单号、退款编号 |
| logistics_work_orders | 15 | issue_type、carrier、problem_tracking_number、shipping_warehouse、order_paid_yuan、resolution、shipping_province/city、work_order_status | 物流异常：问题类型、处理结果 |
| offline_payment_work_orders | 13 | payment_type、refund_issue_type、refund_amount_yuan、alipay_real_name、alipay_account、related_tracking_number、transfer_status、work_order_status | 线下打款：退款金额、支付宝账号、转账状态 |
| replacement_work_orders | 24 | work_order_type、after_sales_reason、sent_product_sku、sent_product_name、quantity、original_tracking_number、replacement_tracking_number、carrier、fulfillment_warehouse、complaint_urgent、work_order_status | 补换货：补发商品、补发单号、是否催办 |

## 风险（risks，派生实体）

风险不是原始业务表，由混合风险引擎在客户上下文上实时计算，跟踪状态落库：

| 字段 | 来源 | 业务含义 |
|------|------|----------|
| risk_id | 派生（buyer_nickname:rule_id） | 风险事件唯一标识 |
| level / category / reason / recommended_action / evidence | risk_engine.assess_context（规则引擎，只读调用） | 等级、类别、命中原因、建议动作、证据 |
| status / note / updated_at | risk_tracking 表 | 人工跟踪状态（待跟进/处理中/已解决）、处理备注 |

## 运行态辅助表（不进入业务 Context）

| 表 | 用途 |
|----|------|
| agent_runs / agent_tasks | Agent 运行审计与任务状态（原则 7） |
| human_feedback | 人机协同留痕（原则 3） |
| import_runs / data_description | 数据导入溯源与原始字典 |

## 隔离与防串线约束

- 会话入口：`conversation_id` → 首条消息确定 `buyer_nickname`，后续全部查询按该买家参数化过滤。
- 订单入口：`order_number` 精确匹配，不回填其他客户数据。
- 客户入口：`buyer_nickname` 精确匹配。
- Context 序列化仅放行上方列出的真实字段（白名单投影），None/空值字段不下发给模型。
