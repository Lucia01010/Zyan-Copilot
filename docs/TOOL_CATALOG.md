# Business Tool Catalog

当前白名单 Tools 及其最小业务用途如下。`human_required_tools` 暂不自动填充，等待第二轮人工 review。

| Tool | 用途 | 输入 | 主要输出 | 适用场景 |
|---|---|---|---|---|
| `get_order` | 精确查询订单 | `order_number: string` | 订单号、商品、赠品、状态、物流号 | 订单、赠品、产品确认 |
| `get_conversation` | 查询单个会话的有限消息 | `conversation_id: string`, optional `limit` | 时间、角色、内容、关联订单/工单号 | 历史承诺、重复进线、情绪趋势 |
| `get_customer_context` | 聚合买家有限订单/消息/工单 | `buyer_nickname: string`, optional `limit` | 经过 compact projection 的客户上下文 | 需要跨订单或跨工单判断 |
| `get_work_orders` | 查询关联售后工单 | `conversation_id` or `order_number` | 工单号、类型、原因、状态、症状/投诉字段 | 不良反应、补发换货、退款、物流异常 |

## Projection policy

Agent runtime 使用 `list_tools(compact=True)`：只返回当前推理需要的字段，不返回整行数据库记录、无关客户字段或完整历史。原始查询 Tools 仍保持可测试，projection 只作用于 Agent tool loop。
