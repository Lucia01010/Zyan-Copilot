# Qwen 真实接入验证

## 配置

```powershell
$env:AGENT_PROVIDER = "qwen"
$env:QWEN_API_KEY = "<your-key>"
$env:QWEN_MODEL = "qwen3.7-plus"
$env:QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:QWEN_TIMEOUT = "30"
$env:QWEN_TEMPERATURE = "0.2"
$env:QWEN_FREE_ONLY = "true"
$env:QWEN_EVAL_TOKEN_BUDGET = "100000"
```

API key 只通过环境变量传入，不写入仓库或日志。

## 回归命令

```powershell
& '.venv\Scripts\python.exe' scripts/evaluate_qwen_live.py
```

脚本会按顺序选择四个最小核心场景：精华过敏/批次、直播赠品、历史承诺冲突、情绪升级。免费保护模式下不并发、不无限重试，每个 case 最多 4 轮模型调用，结果大小受限，不把完整数据库送入模型；达到 `QWEN_EVAL_TOKEN_BUDGET` 会立即停止。每个 case 记录会话标识、Tool 调用顺序、模型 JSON、结构化校验、风险、延迟、逐次 usage、总 token、错误和证据事实 grounding。

已使用项目环境配置实际执行过两轮四场景请求，确认 provider=`qwen`、model=`qwen3.7-plus` 且发生真实 Tool calling。第二轮每个 case 最多执行一次 JSON repair，四个 case 仍未通过 structured JSON 校验；本轮累计 62,718 tokens。结果不计为 PASS，mock 结果同样不计为 live verification。

## 第一轮失败归类

第一轮评估只持久化了解析后的 `model_output` 和错误标签，没有保存原始 final response 内容；因此无法事后可靠区分 prose/fence、单引号、trailing comma、字段漂移或截断。四个 case 的共同可证据失败类型是 `invalid_json`，随后为 `structured_output_invalid`；不能据此臆测具体 a-j 子类。本轮已优先加强 schema contract、原生 `json_object` 请求和一次 bounded repair，而不是继续堆叠无界 parser workaround。

## JSON Schema transport smoke

本轮仅执行 M7 Case A，未执行 B/C/D。provider/model 为 `qwen/qwen3.7-plus`。工具阶段使用 tools，最终合成阶段实际发送 `response_format.type=json_schema`、`strict=true`、Pydantic `AgentOutput` 生成的 schema，`tools=[]`、`tool_choice=none`、`enable_thinking=false`、`stream=false`。真实返回 `finish_reason=length`，final JSON 在 `tools_used` 字段处截断；一次 bounded repair 也失败，因此 Case A 不通过。累计 13,850 tokens。安全诊断请求/响应摘要已写入 gitignored 的 `data/generated/live_debug/`，包含 finish reason、content、tool calls、schema/parser error，不含 API key。

## 输出压缩后的 Case A smoke

仅重新执行 Case A，预算 `25,000`。实际 final `max_tokens=1024`、`output_tokens=964`、内容 `1017` 字符、`finish_reason=stop`，未进入 repair；Pydantic validation、evidence grounding 和真实 Tool calling 均通过。字段统计：`summary` 95 字符、`evidence` 4 条/298 字符、`recommended_actions` 4 条/89 字符、`suggested_reply` 113 字符、`tools_used` 3 项/54 字符、`missing_information` 0 项。case total tokens 为 `12,711`（上轮截断 smoke 为 `13,850`，final output 从 512 增至 964）。

## B/C/D live 回归

本轮未重复 Case A，仅执行 B/C/D，保持同一 JSON Schema 配置。B：`finish_reason=stop`、Pydantic/grounding PASS、repair=false、total `10,937` tokens，订单/工单/赠品证据已由 tools 返回。C：`finish_reason=stop`、Pydantic/grounding PASS、repair=false、total `15,399` tokens，检索了历史会话/承诺；但模型输出 `risk_level=low`，与规则基线 `medium` 不一致，风险提升判断不通过。D：`finish_reason=stop`、Pydantic/grounding PASS、repair=false、total `16,836` tokens，Tool calling 和高风险基线通过。三 case 合计 `43,172` tokens，超过本轮 `40,000` 预算后停止；未继续请求。
