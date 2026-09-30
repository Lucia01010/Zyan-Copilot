# M2 — 业务查询 Tools 与规则风险引擎

## Tools

实现位置：`app/business_tools.py`。`BusinessTools.list_tools()` 返回 Agent 可见的白名单函数：

- `get_order(order_number)`：按字符串订单号查询订单。
- `get_conversation(conversation_id, limit=100)`：按会话 ID 获取有序聊天记录。
- `get_customer_context(buyer_nickname, limit=100)`：聚合订单、消息和五类工单上下文。
- `get_work_orders(conversation_id=None, order_number=None)`：按会话或订单聚合工单，并标注来源表。

所有查询使用参数绑定，不接受任意 SQL；输入缺失或 limit 异常会被约束/拒绝。

## 风险规则基线

实现位置：`app/risk_engine.py`。规则输出统一包含 `rule_id`、`level`、`category`、`reason`、`evidence` 和 `recommended_action`。

- 不良反应工单 → `critical`，要求人工优先处理。
- 客诉加急或异常退货 → `high`。
- 投诉、举报、媒体、12315、明显负面情绪词 → `high`。
- 单次会话消息数达到 20 → `medium`，提示可能重复沟通。
- 客户存在多个订单 → `low`，提示先确认关联订单。

规则优先、可解释，并返回 `requires_human_review`。后续 Qwen 只补充意图/情绪/摘要，不能覆盖明确规则结果。
