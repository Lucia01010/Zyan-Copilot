# Token Cost Audit

本审计只使用已经保存的 M8 live 结果与 debug 元数据，不发起新请求。

## Measured

- LLM-only：N=2，平均 total tokens `973.5`。
- Agent：N=2，平均 total tokens `19,585`。
- Agent/LLM-only 的粗略比值约 `20.1x`；这不是质量结论，只说明工具轨迹和上下文成本很高。
- Agent 平均延迟 `32,813.5ms`，LLM-only `7,084ms`。

## 成本来源拆分

| 部分 | 状态 | 说明 |
|---|---|---|
| initial planning | measured per-request usage available | 每轮 tool completion 的 prompt/completion usage 已记录在 provider usage records；旧 live_results 未完整保留逐轮记录 |
| tool-call loop | measured at case total, detailed split partial | 每次 Qwen completion 都会携带之前的 messages；循环轮数最多 4 |
| tool result payload | estimated contributor | 过去返回整行业务记录，造成 prompt 膨胀；现在 `list_tools(compact=True)` 只投影必要字段 |
| repeated conversation context | estimated contributor | 工具消息会随历史 messages 继续发送；现在请求上下文限制为最近 6 条，tool result 限长 |
| system prompt | estimated small contributor | runtime prompt 已删除比赛说明，只保留执行、证据和 schema 约束 |
| final synthesis | measured in debug | final 阶段单独请求、无 business tools，使用 concise evidence |
| JSON Schema overhead | estimated bounded overhead | schema 必须发送，但字段描述已保持简洁并移除 title/default |

## 优化状态

- 已实现工具结果 projection、消息顺序修复、最近消息窗口和 final evidence-only synthesis。
- P0 目标单 case `<15k` 尚未在历史 Agent N=2 上稳定达到；历史平均约 `19,585`。
- P1 `<10k` 和 stretch `5k–8k` 尚未证明，不将估算写成 measured。
- 下一轮离线 replay 应比较 compact projection 前后的 prompt 字符数和估算 token；未经新的 live 请求不宣称真实 token 降幅。
