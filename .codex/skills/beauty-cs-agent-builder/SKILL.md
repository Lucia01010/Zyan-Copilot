---
name: beauty-cs-agent-builder
description: 持续开发当前 Beauty Techathon 美妆客服 AI Agent 项目，涵盖比赛材料分析、业务数据建模、Qwen Agent、风险引擎、FastAPI 后端、React/TypeScript 工作台与风险看板，并以可运行、可测试的 MVP 为完成标准。
metadata:
  short-description: 构建 Beauty Techathon 美妆客服 AI Agent
---

# Beauty CS Agent Builder

用于本仓库的持续工程开发。目标是交付知妍 AI（Zhiyan Beauty Copilot）比赛 Demo：React 模拟千牛客服工作台右侧知妍·伴答插件、独立知妍·洞察风险预警跟踪看板，二者共享 FastAPI + SQLite + 知妍·智核（Qwen Agent + Tools + 混合风险引擎）。根据官方答疑，真实千牛生产部署不是比赛完成前提。

## 工作方式

- 先检查仓库现状、`docs/PROJECT_STATE.md`（若存在）和 `data/raw/`。比赛原始材料只读，禁止覆盖、重命名或改写；解析结果写入应用目录或生成的文档。
- 一次性盘点并缓存文件清单、表头、字段映射和业务规则，后续复用已确认结论，避免重复读取和重复 Prompt。只有源文件变化或证据不足时才重新解析。
- 先形成最小闭环：真实赛题数据导入/查询 → 风险判定 → Agent 工具调用 → API → React 模拟工作台 `/workbench` → `/risk-dashboard` → 自动测试。不要过早引入微服务、Redis、Kafka、复杂 RAG、多 Agent 或模型微调。
- 采用官方允许的验证方式：Vibe Coding 模拟客服工作台，或场景数据模拟 + Agent 结果展示 + 插件交互 Demo。重点验证产品交互、真实客服流程、Agent 能力和风险闭环，而不是复杂的千牛商家接入。
- 工程问题由 Codex 自行决策；只有缺少会改变产品范围、凭证或破坏性操作授权时才询问用户。
- 每个阶段更新 `docs/PROJECT_STATE.md`：完成项、假设、运行命令、测试结果、已知风险、下一步和数据来源。不存在则创建；不要把原始材料复制到其中。

## 技术基线与边界

- MVP：Python 3.11、FastAPI、SQLite、React、TypeScript。按仓库现状选择轻量前端方案。
- Qwen 通过环境变量配置，并使用 OpenAI-compatible endpoint。至少支持 `QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL`，密钥只读环境变量，不写入代码、日志或提交物。没有凭证时提供 deterministic/mock provider，使测试仍可运行。
- 后端负责统一数据访问、业务查询 Tools、Agent 编排、风险引擎和审计/评估信息；前端只通过 API 访问，不直接读 SQLite。
- 风险引擎采用可解释的混合策略：规则/阈值先行，模型补充分类或摘要；输出必须包含风险等级、命中原因、证据字段和建议动作。
- API、数据库和前端代码应可被本地命令启动；CORS、错误响应、健康检查和配置校验有最小实现。
- 真实千牛接入、商家账号、开放平台权限和生产部署均为 OPTIONAL enhancement；不得因缺少真实店铺或平台资质阻塞比赛 Demo 完成。只有用户明确要求且具备相应资质/权限时，才进入 M12 Real Qianniu Integration。

## 推荐执行顺序

1. 阅读并结构化比赛源文件与业务 Excel；记录字段、样例、日期/金额处理和不确定项。不要修改源文件。
2. 设计 SQLite schema、幂等导入和核心查询 Tools，并用 fixture/脱敏样例测试。
3. 实现混合风险引擎和 Qwen Agent。Agent 只能调用白名单 Tools；记录 token、模型、耗时和失败原因，不记录密钥或无必要敏感文本。
4. 实现 FastAPI：健康检查、会话/客服建议、风险列表/详情/状态更新、评估/成本统计等端点，并补 API 测试。
5. 实现 React + TypeScript：`/workbench` 展示知妍·伴答会话上下文、智能回复建议、风险提示和人工接管；`/risk-dashboard` 展示知妍·洞察筛选、等级、关键依据、状态和跟踪动作。空数据、加载、错误和 mock 模式可用。
6. 运行自动测试、lint/typecheck（若已配置）、启动 smoke test；失败时定位并自动修复，再次运行。未完成运行和测试不得宣称完成。
7. 评估工具调用、风险样例、可解释性、延迟和 token 成本，并把结果写入状态文档。

## Roadmap

- M0–M8：数据、SQLite、业务 Tools、Agent、混合风险、工作台、看板和受预算保护的评估闭环。
- M9 — Product / Demo Polish：完善交互、视觉层级、错误/空态、演示路径和可解释性。
- M10 — Competition Demo Packaging：打包可运行比赛 Demo，不依赖真实千牛生产权限。
- M11 — Real Scenario Driven Simulated Qianniu Plugin Runtime：将 `/workbench` 明确拆为模拟千牛客服工作台宿主与知妍·伴答插件；交互由模拟 Host 提供，但会话、订单、工单、风险和 Gold 场景必须来自真实赛题数据。
- M12 — Optional Real Qianniu Integration：仅在用户明确要求并具备真实店铺、商家账号和开放平台权限时实施；不是比赛完成前提。

## M10 完成定义

M10 必须能在本地一键或最少步骤启动，并完整演示：模拟消费者咨询、模拟人工客服工作台、右侧 Agent 插件、风险事件写入风险看板、风险状态跟踪、稳定演示场景和演示说明。真实千牛部署不属于 M10 blocker。

## 资源路由

- 产品范围、共享架构、数据流和非目标：阅读 [references/PRODUCT_SPEC.md](references/PRODUCT_SPEC.md)。
- 完成定义、自动验收、演示路径和质量门槛：阅读 [references/ACCEPTANCE.md](references/ACCEPTANCE.md)。
- 仅在对应阶段读取相关参考，避免每轮重复加载全部材料。

## 完成判定

以 `references/ACCEPTANCE.md` 为准。必须有可复现的启动命令、测试输出和已知限制；仅生成代码、截图或静态页面不算完成。外部 Qwen 不可用时，明确标注并用 mock provider 验证其余闭环。
