# 客服行动目录（M16）

本目录来自当前导入的 998 条 `chat_messages` 及订单、物流、售后工单表。客服历史回复中可观察到的主要动作包括：订单核对、物流/签收查询、退款/打款跟进、退货、补发/换货、赠品/承诺回看、不良反应登记和历史沟通复核。目录只把当前 SQLite 中有真实来源且有后端工具的动作标为可执行。

## 可执行 Action

| action_id | 展示名称 | 典型问题/场景 | 数据来源 | backend tool | 返回重点 | 当前 |
|---|---|---|---|---|---|---|
| `check_order` | 查看订单信息 | 订单、商品、赠品、普通咨询 | `orders` | `get_order_info` | 订单号、商品、状态、金额、物流单号 | true |
| `check_logistics` | 查看物流信息 | 未收到、发货、签收、快递 | `orders` + `logistics_work_orders` | `get_logistics_info` | 承运商、运单号、状态、物流工单 | true |
| `check_refund` | 查看退款状态 | 退款、售后单关闭、到账 | 退货/线下打款工单 | `get_refund_status` | 退款原因、金额、工单/转账状态 | true |
| `check_payment` | 查看打款状态 | 线下打款、支付宝到账 | `offline_payment_work_orders` | `get_payment_status` | 打款金额、状态、编号 | true |
| `check_return` | 查看退货进度 | 退货、仓库签收 | `after_sales_return_work_orders` | `get_return_status` | 退货物流、退款编号、状态 | true |
| `check_replacement` | 查看换货状态 | 换货、漏发、少件、补发 | `replacement_work_orders` | `get_replacement_status` | 换货商品、补发状态、物流 | true |
| `check_ticket` | 查看售后工单 | 售后、投诉、工单跟进 | 五类工单表 | `get_ticket_status` | 工单类型、状态、处理结果 | true |
| `check_adverse_reaction` | 查看不良反应记录 | 发红、瘙痒、刺痛、过敏 | `adverse_reaction_work_orders` | `get_adverse_reaction_record` | 症状、登记状态、工单编号 | true |
| `check_service_history` | 查看历史沟通 | 重复进线、投诉、历史服务 | `chat_messages` | `get_service_history` | 当前会话历史消息 | true |
| `check_service_promises` | 查看历史服务承诺 | 赠品、补发、回访、承诺 | `chat_messages` | `get_service_promises` | 包含承诺/回访的原始消息 | true |

## 真实数据边界

每个 Action 都绑定当前 `session_id`，工具返回 `status=NOT_FOUND` 时，插件显示“当前比赛实例数据未找到相关记录，我会帮您进一步核实”，不生成假物流节点、预计到达时间、生产批次或直播后台数据。当前没有独立直播后台、生产淘宝 API、批次追溯或人工主管分派工具，因此这些不作为可点击 Action。

## 从数据挖掘到按钮

推荐器使用当前会话最近消息的关键词和真实上下文，将按钮限制为 1–4 个；按钮通过 `BusinessToolRegistry`（本文件的 Action 定义）进入后端工具，再由数据库投影结果生成 Agent Chat 文案。Qwen 可在 live 模式参与推荐，但不得发明 `action_id` 或 `tool_name`。
