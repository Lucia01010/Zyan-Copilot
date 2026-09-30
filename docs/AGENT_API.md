# M3 — Qwen Agent 与 FastAPI

## Qwen Provider

`app/qwen_agent.py` 提供 Qwen provider 与知妍·智核 Agent Runtime（代码中的 `BeautyAgent` 保持不变）。

- `AGENT_PROVIDER=mock|qwen` 控制 provider；缺少配置时默认 mock，`QWEN_MOCK=1` 仍兼容旧配置。
- `QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL`、`QWEN_TIMEOUT`、`QWEN_TEMPERATURE` 通过环境变量读取。
- 远程模式调用 OpenAI-compatible `/chat/completions`，使用现有白名单 Tools 的 bounded tool-calling loop，最多 4 轮。
- 真实模式要求 `QWEN_API_KEY`，结构化 JSON 必须包含 intent、emotion、summary、evidence、risk_level、recommended_actions、suggested_reply（前端称为智能回复建议）；证据只允许来自 Tool 返回结果。
- 每次运行写入 SQLite `agent_runs`，保存 provider、模型、token、耗时、工具调用和风险等级，不保存密钥。

## FastAPI

`app/api.py` 提供：

- `GET /health`
- `POST /api/workbench/suggest`
- `GET /api/evaluation/costs`

运行依赖见 `requirements.txt`。当前环境未预装 FastAPI，因此 API 模块会安全地保持未激活状态，并在安装依赖后自动创建应用；Agent mock 闭环和核心测试不依赖网络或远程模型。
