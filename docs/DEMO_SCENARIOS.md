# Competition Demo Scenarios

These scenarios use existing source-derived sessions and generated risk events. They are fixed references for recording and judging; no raw source files are modified.

## A — 不良反应与历史服务风险（主场景）

- Session/customer: `S00082` / source-derived customer context.
- Opening question: 消费者反馈使用美妆产品后出现不适，要求客服核对售后处理。
- Evidence to show: conversation history, related order, adverse-reaction work order, service timeline and rule findings.
- Agent tools: `get_customer_context`, `get_conversation`, `get_order`, `get_work_orders` as selected by the Agent.
- Risk result: high/critical rule evidence with human-review recommendation; final hybrid risk is shown separately from model risk.
- Recommended actions: human takeover, verify symptoms/stop-use/medical status, and avoid unsupported medical conclusions.
- Dashboard event: adverse-reaction risk event for the same customer context, initially `open`.
- Expected result: judge can see why the Agent escalates and can update the event to `processing`.

## B — 普通订单/赠品咨询（对照场景）

- Session/customer: `S00002`.
- Opening question: 消费者咨询套装搭配和赠品内容。
- Evidence to show: product/offer messages, order context when available, short timeline and no high-risk finding.
- Agent tools: primarily `get_customer_context` / `get_conversation`; order lookup only when an order is present.
- Risk result: low or no escalation; the workbench still provides a concise reply and next action.
- Recommended actions: answer the product question, confirm the promised gift, and close the conversation when resolved.
- Dashboard event: use the matching low context event only if it is present; otherwise explain that no risk event is created for a resolved consultation.
- Expected result: demonstrate the Agent supports routine service, not only escalation.

## C — 物流/重复服务问题（闭环场景）

- Session/customer: `S00075`.
- Opening question: 消费者追问物流/售后处理进度，并引用此前客服承诺。
- Evidence to show: recent messages, order/物流 information, work-order history, promise language and service timeline.
- Agent tools: `get_customer_context`, `get_work_orders`, `get_order`, and bounded conversation history retrieval.
- Risk result: rule risk may be critical when related safety evidence exists; current live hybrid result for the selected run was `HIGH` with a `HIGH` rule floor.
- Recommended actions: confirm the single unresolved issue, verify work-order outcome, communicate a time-bound next step, and hand over when required.
- Dashboard event: select the matching customer event, open details, then update status from `open` to `processing`.
- Expected result: reproduce the verified path `conversation → Agent analysis → risk event → evidence/timeline → tracked status`.
