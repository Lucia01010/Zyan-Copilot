# 知妍 AI

## Zhiyan Beauty Copilot

知妍 AI 是面向美妆客服场景的智能接待与风险洞察 Copilot。知妍 AI 通过大模型 Agent 理解消费者需求，结合订单、物流、历史服务等业务信息，为客服提供实时辅助，并帮助企业发现和跟踪服务风险。

产品模块：知妍·伴答（智能接待辅助插件）、知妍·洞察（风险预警与跟踪看板）、知妍·智核（Agent Runtime、业务 Tools 与 Hybrid Risk Engine）。

本项目使用真实赛题数据、SQLite 业务 Tools、Qwen Agent 和 Hybrid Risk，提供 React 模拟千牛工作台 `/workbench` 与知妍·洞察 `/risk-dashboard`。按照官方答疑，比赛不要求真实千牛生产部署。

## Architecture

`React simulated workbench + risk dashboard → FastAPI → SQLite/business Tools → Qwen Agent or cached/mock provider → Hybrid Risk`

真实千牛商家接入属于可选 M11，不是本 Demo 的完成条件。

## Windows 比赛 Demo 最短启动步骤

首次使用先完成环境准备：

```powershell
Copy-Item .env.example .env
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

日常启动只需**双击 `scripts/start_zhiyan.cmd`**（单进程：后端同时托管已构建的前端，自动打开浏览器），访问 `http://localhost:8000/workbench` 或 `http://localhost:8000/risk-dashboard`，健康检查为 `http://127.0.0.1:8000/health`。默认 `DEMO CACHED MODE`，不依赖 Qwen 网络。

> 前端代码改动后，在 `frontend/` 执行 `npm run build`，刷新 8000 页面即可生效；需要热更新开发体验时再用 `npm run dev`（5173）。

## Demo Mode 与 Live Qwen Mode

- **DEMO CACHED MODE**：`AGENT_PROVIDER=mock`、固定 SQLite 场景和前端离线 fallback，适合比赛现场和视频录制；UI 必须保留模式标识，不冒充实时模型。
- **LIVE QWEN MODE**：显式设置 `AGENT_PROVIDER=qwen`、`QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL` 后使用 OpenAI-compatible endpoint。网络/API 失败时由人工明确切换回 Demo Mode，不自动静默伪装。

重置演示状态（不会修改 `data/raw`）：

```powershell
& '.venv\Scripts\python.exe' scripts/reset_demo.py
```

启动前检查：

```powershell
& '.venv\Scripts\python.exe' scripts/demo_preflight.py
```

默认 `AGENT_PROVIDER=mock`，日常 UI 开发和普通测试不会调用远程模型。远程 Qwen 只在明确设置 `AGENT_PROVIDER=qwen` 并运行 live evaluation/smoke 时调用，使用 `.env` 中的 OpenAI-compatible endpoint 配置。比赛开发阶段默认 `QWEN_FREE_ONLY=true`：只运行有限串行 case、每 case 最多 4 轮、`QWEN_MAX_TOKENS` 默认 512，并由 `QWEN_EVAL_TOKEN_BUDGET=50000` 保护总额度；遇到 quota/billing/余额不足会立即停止，不切换其他模型或付费路径。不要提交 `.env` 或任何 API Key。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Set-Location frontend
npm run typecheck
npm run build
```

后端、前端和知妍·洞察的 smoke 验收证据记录在 `docs/PROJECT_STATE.md`；比赛场景和操作路径见 `docs/DEMO_SCENARIOS.md`、`docs/DEMO_SCRIPT.md`。

## 常见问题

- **没有 Qwen 凭证怎么办？** 使用 `scripts/start_demo.ps1` 的 Demo Mode；不要把 `.env.example` 占位符当作凭证。
- **端口被占用怎么办？** 停止已有的 uvicorn/Vite 进程，或手工启动并同步 CORS/前端 API 地址。
- **为什么页面显示 cached？** 这是可复现的比赛演示结果，不是实时 Qwen 响应。
- **是否必须接入千牛生产环境？** 不需要；真实接入是可选 M11。

项目状态和 milestone 验收见 `docs/PROJECT_STATE.md` 与 `.codex/skills/beauty-cs-agent-builder/references/ACCEPTANCE.md`。
