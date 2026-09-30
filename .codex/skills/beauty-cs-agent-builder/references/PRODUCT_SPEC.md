# 知妍 AI（Zhiyan Beauty Copilot）产品规格

## 目标

知妍 AI 提供两个入口：`/workbench` 以 React 模拟千牛客服工作台承载知妍·伴答智能接待插件，读取会话和客户/订单上下文，生成可编辑智能回复建议与风险提示；`/risk-dashboard` 由知妍·洞察集中展示风险事件、关键依据、状态和跟踪动作。两者共享知妍·智核、FastAPI、SQLite、Qwen Agent 和风险引擎。根据赛题官方答疑，比赛允许使用 Vibe Coding 模拟客服工作台，真实千牛生产部署不是完成前提。

## 比赛交付路线

默认路线是：真实赛题数据 + React 模拟千牛工作台 + 知妍·伴答 + 真实 Qwen Agent（无凭证时保留明确标识的 mock）+ 知妍·洞察 + 完整端到端交互闭环。产品交互设计、真实客服流程理解、知妍·智核工具调用和风险闭环是核心验收对象。

真实千牛商家接入、生产部署、开放平台授权和店铺账号属于 M11 `Optional Real Qianniu Integration`，不是 MVP、M9 或 M10 的 blocker。

## 共享架构

```text
React routes (/workbench, /risk-dashboard)
        ↓ HTTP/JSON
FastAPI routes + validation + error handling
        ↓
Application services ── SQLite repositories
        ├─ business query tools
        ├─ hybrid risk engine (rules + optional Qwen)
        └─ Qwen Agent (OpenAI-compatible endpoint or mock)
```

## 最小领域模型

- `customer`：客户标识、会员/画像信息、历史摘要。
- `conversation` / `message`：会话、角色、文本、时间。
- `order` / `order_item`：订单、金额、状态、商品与售后。
- `product`：商品、功效/使用限制、关键属性。
- `risk_event`：等级（low/medium/high/critical）、类别、原因、证据 JSON、状态（open/processing/resolved/ignored）、时间与跟踪人。
- `agent_run`：请求标识、模型、token 输入/输出、耗时、工具摘要、错误；不含密钥和无必要敏感文本。

实际 schema 可按源数据调整，但保留主键、创建/更新时间、幂等导入和必要索引。

## Roadmap 边界

- M9 — Product / Demo Polish：打磨模拟工作台、看板、演示路径和可解释性。
- M10 — Competition Demo Packaging：形成可一键启动、可稳定演示的比赛 Demo。
- M11 — Real Scenario Driven Simulated Qianniu Plugin Runtime：`/workbench` 由模拟千牛客服工作台宿主和独立知妍·伴答插件组成；宿主模拟交互，业务上下文必须来自真实赛题 session/order/ticket/risk 数据。
- M12 — Optional Real Qianniu Integration：仅在明确提出且具备真实资质/权限时评估和实施。

## 业务查询 Tools

Tools 是小而可测试的白名单函数，例如查询客户摘要、订单状态/售后、商品使用说明、历史案例和风险事件。每个 Tool 定义输入 schema、数据范围、结构化输出和失败响应；Agent 不得拼接任意 SQL。

## 风险与 Agent

风险规则覆盖源材料支持的投诉升级、退款/退货异常、过敏/不良反应、功效或合规承诺、重复高风险客户等场景。规则命中先产生证据；Qwen 只做意图/情绪/摘要补充，不能覆盖明确规则。建议回复标注依据和“需人工确认”条件。

## API 最小契约

- `GET /health`
- `GET /api/customers/{id}/summary`
- `GET /api/orders/{id}`
- `GET /api/products/{id}`
- `POST /api/workbench/suggest`
- `GET /api/risks`、`GET /api/risks/{id}`
- `PATCH /api/risks/{id}`
- `GET /api/evaluation/costs`

响应使用稳定 JSON 结构、可读错误信息和请求标识；前后端字段命名一致。

## 配置

用环境变量配置数据库路径、CORS、Qwen endpoint/model/key/timeout 和 mock 开关。提供 `.env.example`，不提交真实密钥。远程模型不可用时，mock provider 产生固定、可测试的结构化结果。
