# 知妍 AI（Zhiyan Beauty Copilot）项目状态

## 当前阶段

M5 PASS（MANUAL_BROWSER_ACCEPTANCE）；M6 PASS；M7 PARTIAL — live Agent pipeline verified, one risk-consistency issue remains；M8 小规模 Hybrid live evaluation 已完成；M9 Product / Demo Polish PASS；M10 Competition Demo Packaging PASS。真实千牛接入改为 M11 Optional，不是比赛完成前提。

## 已完成

- 创建仓库级 `AGENTS.md`。
- 创建 `.codex/skills/beauty-cs-agent-builder/` 及其产品规格、验收标准。
- 初始化 Git 仓库并添加根目录 `.gitignore`。
- 完成 M0 源文件盘点，建立 `docs/SOURCE_INVENTORY.md`。
- 完成 M1 SQLite schema，建立 `docs/DATA_SCHEMA.md`。
- 创建 `scripts/import_excel_to_sqlite.py` 和 `tests/test_import_excel_to_sqlite.py`。
- 已生成 `data/beauty_cs_agent.sqlite3` 与导入摘要 `data/import_summary.json`。
- 建立 `app/business_tools.py`、`app/risk_engine.py` 和 `docs/BUSINESS_TOOLS.md`。
- 业务 Tools 采用白名单和参数绑定，风险规则保留证据与建议动作。
- 建立 `app/qwen_agent.py`、`app/api.py`、`requirements.txt` 和 `docs/AGENT_API.md`。
- Agent 支持 `QWEN_MOCK` 离线模式与 OpenAI-compatible Qwen endpoint，并记录 `agent_runs` 成本元数据。
- 建立 `frontend/` Vite + React + TypeScript 应用和 `docs/FRONTEND.md`。
- 完成 `/workbench` 智能接待辅助和 `/risk-dashboard` 风险筛选界面，API 不可用时提供 mock fallback。
- 创建项目 `.venv`，安装后端依赖并生成 `frontend/package-lock.json`。
- 完成真实后端 API、前端 typecheck、Vite production build 和开发服务器 smoke test。
- 建立 `docs/ENVIRONMENT_REPORT.md`、`.env.example`、`README.md`、`scripts/setup.ps1` 和 `scripts/dev.ps1`。
- M5 补齐 `/api/workbench/sessions`、会话详情和 CORS；工作台展示会话列表、聊天、intent、emotion、evidence、订单/工单、timeline、risk、recommended actions 和 suggested reply。
- 用户人工完成 M5 浏览器验收：`/workbench` 打开、会话加载/切换、聊天显示、AI 分析、插件字段展示和运行稳定性均通过。
- M6 已建立风险详情、证据、筛选和状态跟踪 API/UI，状态持久化到 SQLite `risk_tracking`。
- M6 建立 `scripts/smoke_risk_api.py`，验证风险列表、详情字段和状态持久化恢复。
- M7 扩展 `scripts/evaluate_mvp.py`，完成 112 个客户样例的 mock Agent、Tools、风险和 Token 评估，报告见 `docs/EVALUATION_REPORT.md`。
- 完善 `QwenProvider` 的 `AGENT_PROVIDER=mock|qwen` 切换、OpenAI-compatible bounded tool-calling、结构化 JSON 校验和证据 grounding 检查；新增 `scripts/evaluate_qwen_live.py` 与 `docs/QWEN_LIVE_VERIFICATION.md`。
- 新增 `QWEN_FREE_ONLY=true`、`QWEN_EVAL_TOKEN_BUDGET=50000`、`QWEN_MAX_TOKENS` 和 `QWEN_MAX_TOOL_ROUNDS` 保护；live evaluation 串行执行、限制调用轮数和结果大小，记录逐次 usage 与总 token，额度/计费错误立即停止且不切换模型。
- M8.0 建立 `TokenBudgetGuard`，在启动下一 live case 前按保守估计检查剩余预算；新增 M8 dataset/evaluator、指标 provenance 与 `docs/EVALUATION_PLAN.md`、`docs/EVALUATION_REPORT.md`。

## 当前假设

- `data/raw/` 中的比赛源文件保留并纳入版本控制；当前未发现需要因体积排除的文件。
- 本地数据库、环境文件、缓存、虚拟环境和前端依赖不纳入版本控制。

## 待办

- M9：Product / Demo Polish。
- M10：Competition Demo Packaging，默认比赛交付终点。
- M11：Optional Real Qianniu Integration，仅在用户明确要求且具备真实店铺、商家账号和开放平台权限时启动。
- 不因缺少真实店铺、商家账号或开放平台权限阻塞比赛项目完成。

## 官方答疑路线调整（2026-09-29）

- 赛题 1 插件无需强制部署到千牛生产环境。
- 允许使用 React/Vibe Coding 模拟客服工作台，或使用场景数据模拟 + Agent 计算结果展示 + 插件 Demo 产品交互逻辑。
- 默认交付路线为：真实赛题数据、React 模拟千牛工作台、真实 Qwen Agent、风险预警看板和完整端到端风险闭环。
- M10 完成标准包括模拟消费者咨询、模拟人工客服工作台、右侧 Agent 插件、风险事件写入看板、风险状态跟踪、稳定演示场景、一键启动和演示说明。
- 真实千牛接入仅为 M11 可选增强；除非用户明确要求并提供真实资质/权限，否则不进入 M11。

## 验证记录

- `python scripts/import_excel_to_sqlite.py --db data/beauty_cs_agent.sqlite3`：通过。
- `python -m unittest discover -s tests -v`：1 个测试通过。
- 重复导入后业务表行数保持稳定，`import_runs` 正确累计运行记录。
- 已抽查 `orders.order_number`，值为 Python/SQLite 字符串且未出现科学计数法。
- `python -m unittest discover -s tests -v`：5 个测试通过。
- 已对真实数据库客户样例执行 Tools 聚合与风险评估 smoke test，返回结构化 context/risk 结果。
- `python -m unittest discover -s tests -v`：6 个测试通过，包含 mock Agent 与成本记录验证。
- Python/FastAPI/uvicorn 和前端依赖已恢复并完成真实验证，详细结果见 `docs/ENVIRONMENT_REPORT.md`。
- 环境恢复后已重新执行相关检查；完整结果见 `docs/ENVIRONMENT_REPORT.md`。
- `MANUAL_BROWSER_ACCEPTANCE`：用户人工验证 `/workbench` 全流程通过；未执行自动化 CUA，也未执行自动化 console 检查。
- M5 使用 mock provider 完成 UI 验收；真实 Qwen 验证尚未完成，但不作为 M5 UI 验收 blocker。
- M6：`scripts/smoke_risk_api.py` 返回 `status_persistence: ok`；前端 `npm run typecheck` 与 `npm run build` 通过。未声称本轮执行风险看板浏览器 click-through。
- M7：`scripts/evaluate_mvp.py` 评估 112 个客户，42 个风险发现，Tool 成功率 100%，mock 输入/输出 token 为 705,633/2,760；`python -m unittest discover -s tests -v` 修复后通过 7 个测试。
- 真实 Qwen 回归命令在无凭据时明确返回阻塞信息（退出码 2，未发起网络请求）；未执行四场景 live test。离线编译与 `python -m unittest discover -s tests -v`：9 个测试通过。

## 已知限制

- 当前数据库是 M1 原始业务层，尚未建立后续 service 层的规范化客户、商品和风险事件实体。
- 原始 DOCX 的文本已读取；case 图片已人工盘点要点，尚未做 OCR。
- 当前 PowerShell PATH 尚未刷新 npm，需使用 `C:\Program Files\nodejs\npm.cmd` 或重开终端。
- CUA 曾返回 `Transport closed`；该浏览器自动化基础设施限制不代表当前代码失败。
- 真实 Qwen 回归凭证已通过环境配置提供，但 M3/M7 live-model verification 尚未通过，不把 mock 结果计为真实模型通过。
- 免费额度保护已默认开启；只有显式 `AGENT_PROVIDER=qwen` 且运行 live evaluation/smoke 才会调用真实 Qwen。
- 真实 Qwen 回归已执行第二轮：provider/model 为 `qwen/qwen3.7-plus`，四个 case 均发生真实多轮 Tool calling；每个 case 最多执行一次 bounded JSON repair，但仍出现 `invalid_json`/`json_repair_failed`/`structured_output_invalid`，本轮累计 `62,718` tokens，未标记 PASS。已通过 Pydantic schema、JSON-only prompt、`response_format=json_object`、结果截断和 repair 单元测试；当前不再追加 live 请求，M7 live verification 保持未完成。
- JSON Schema transport smoke 曾仅执行 Case A 并发现长度截断；随后已通过压缩修复。安全诊断写入 `data/generated/live_debug/`（gitignored）。
- 输出长度压缩后 Case A smoke PASS：`max_tokens=1024`、`output_tokens=964`、`finish_reason=stop`、未 repair，Pydantic validation、Tool calling 与 evidence grounding 均通过，total `12,711` tokens。
- 随后仅执行 B/C/D：B 与 D 的真实 Tool calling、strict schema、Pydantic、grounding 和 finish_reason 均通过；C 虽 schema/grounding 通过，但模型 risk_level=low 与 medium 规则基线不一致。三 case 合计 `43,172` tokens，超过 `40,000` 预算后停止，M7 四场景 live verification 未标记 PASS，未进入 M8。
- M7 状态修正为 `PARTIAL — live Agent pipeline verified, one risk-consistency issue remains`；A/B/C/D 均真实 qwen/tool calling/structured output/grounding，通过但 Case C 风险分歧保留。
- M8 离线阶段：已生成可追溯 source-derived dataset、Rules baseline 报告和三系统评估框架；人工风险/意图标签不可用，未伪造 accuracy/F1。
- M8.0–M8.7 离线准备验证：dataset 138 条会话、source label coverage 138/138；修正业务 Tools 的工单来源标记后 Rules distribution 为 low=102/medium=3/high=22/critical=11；`TokenBudgetGuard` 与 dataset provenance 测试通过；未发起新的 Qwen 请求。
- 人工 gold 阶段：生成 24 条分层候选 CSV，覆盖 LOW/MEDIUM/HIGH/CRITICAL、A/B/C/D 关键会话；当时提供 `docs/MANUAL_EVALUATION_GUIDE.md` 与 `scripts/review_manual_gold.py`，人工未完成前不计算正式 accuracy 或 Agent improvement。随后人工完成 intent/risk/status 字段，生成 Gold v1；required_tools/notes 仍为空。
- 修复人工候选会话顺序：`message_sequence` 按整数并结合 `_row_number` 升序，excerpt 保留时间、角色和内容。旧 CSV 因检测到 3 个非空人工字段已备份为 `manual_gold_candidates.pre_order_fix.csv`，修正版重新生成并随机抽查 5/5 通过。
- M8.8 Gold v1：24/24 条人工标注为 DONE，生成 `manual_gold_v1.jsonl`；未填充 required_tools/notes。
- M8.11–M8.16 小规模 live 对照：仅执行 2 条（含 Case C），LLM-only 与 Agent 均使用真实 qwen3.7-plus；总 41,117 tokens，第三条由 predictive guard 阻止。结果见 `data/generated/evaluation/live_results.jsonl`、`metrics.json` 和 `docs/EVALUATION_REPORT.md`。

## M8 当前修订（离线优化，2026-09-29）

- Gold Set v1 已固化：24/24 条 `human_review_status=DONE` 纳入正式 Gold；Case C 的正式人工标签为 `HIGH`，不再标记为未知或待审核。`human_required_tools` 与 `human_review_notes` 仍按人工决定保持为空。
- 已建立统一 IntentTaxonomy：来自 Gold v1/source 标签，支持 major/minor 合法组合、别名归一化和非法组合测试，见 `docs/INTENT_TAXONOMY.md`。
- 已实现离线 Hybrid Risk policy：保留 `model_risk`、`rule_risk`、`rule_floor`、`final_risk`，只对有证据支持的明确不良反应、投诉/监管升级、历史承诺线索应用可解释风险下限；不针对 Case C 硬编码结果。
- 已完成 Agent token cost audit、业务 Tool projection/context compaction 方案和 Tool catalog，见 `docs/TOKEN_COST_AUDIT.md`、`docs/TOOL_CATALOG.md`。
- 历史 N=2 live 结果生成于 hybrid policy 实现前，未重新调用 Qwen；因此 hybrid 与人工 Gold 的正式 live 指标仍为未测量，而非通过或失败。
- 本轮离线验证：`python -m unittest discover -s tests -q`，24/24 PASS；未发起新的 live Qwen 请求。
- M8 Hybrid live evaluation 尝试：按 90,000 token 硬预算、30,000 token/样本保守估算启动前检查；因仓库根目录没有 `.env` 且进程未提供 `QWEN_API_KEY`，在发起 HTTP 请求前安全停止。未使用 `.env.example` 占位符，未覆盖既有 live 结果。
- 随后凭证恢复后的重试：发现本机 `HTTP(S)_PROXY=127.0.0.1:9` 导致连接拒绝；仅在当前进程清除代理后直连，endpoint 返回 HTTP 401 Unauthorized。未产生 token、未追加 live 结果、未 fallback mock 或其他模型；需核对 Qwen API key 与 endpoint/region 匹配后再重试。
- 更新 `QWEN_BASE_URL/region` 后再次重试仍在首个 LLM-only 请求返回 HTTP 401（model=`qwen3.7-plus`）；未产生 token、未追加结果，按失败策略停止。
- 再次更新凭证与 endpoint 后，首个请求返回 HTTP 404 Not Found（model=`qwen3.7-plus`）；未产生 token、未追加结果，需核对兼容 API 路径与模型区域，不再扩大重试。
- M8 Hybrid live evaluation 成功：使用更新后的 endpoint/key，按 `QWEN_FREE_ONLY=true`、90,000 token 硬预算和 30,000 token/样本预测估算执行 3 条（Case C、LOW、CRITICAL），实测总 42,183 tokens，未启动第 4 条；结果追加至 `live_results.jsonl`，未覆盖既有记录、未 fallback。
- 最新 3 条 Agent：structured output 3/3、grounding 3/3、unsupported fact 0、repair 0、finish_reason 全为 stop；平均 13,013 tokens、20,892ms。相对历史 19,585 tokens/case，下降约 33.6%。Hybrid risk 3/3 有 final risk，Risk accuracy=1.00（N=3）；Rules=0.67，LLM-only=1.00，Agent model=1.00。Case C 最新结果 Human HIGH / Rules CRITICAL / rule floor HIGH / model HIGH / hybrid HIGH。
- `metrics.json` 与 `docs/EVALUATION_REPORT.md` 已更新；planning/tool-loop/final 分阶段 token 未由本次 evaluator 持久化，明确标为 NOT MEASURED。

## M9 Product / Demo Polish（PASS）

- 模拟工作台顶部增加演示/在线模式标识和产品说明，明确当前交付是 React 模拟千牛工作台。
- 工作台补充会话加载态、无会话态、无消息态、角色标签、分析结果空态和人工接管/复制反馈，降低演示时的状态歧义。
- Agent 建议回复支持浏览器复制反馈；人工接管动作给出明确 toast，不改变后端业务状态。
- 前端验证：`C:\Program Files\nodejs\npm.cmd run typecheck` 通过；`C:\Program Files\nodejs\npm.cmd run build` 通过（Vite production build）。
- 后端离线验证：`python -m unittest discover -s tests -q`，25/25 PASS。
- M9 浏览器验收已完成：使用 mock/demo 模式实际打开 `/workbench` 与 `/risk-dashboard`；会话切换、角色/消息展示、AI 分析、插件字段、复制反馈、人工接管反馈、风险指标卡、筛选、详情证据/服务轨迹和状态持久化均通过。完成同一 `郭a**` 会话 → Agent 分析 → 对应风险事件 → 看板详情 → `processing` 状态保存/刷新闭环。
- 浏览器 fresh tab console error=0；未发现用户可见 runtime error 或阻塞性 network failure。此前发现并修复 5174 开发端口未在 FastAPI CORS allowlist 的问题。
- M9 验证命令：frontend typecheck PASS；Vite production build PASS；`python -m unittest discover -s tests -q` 25/25 PASS。未发起 live Qwen evaluation。

## M10 Competition Demo Packaging（PASS）

- 固化 3 个真实赛题数据演示场景：`docs/DEMO_SCENARIOS.md`，覆盖不良反应/历史服务风险、普通套装赠品咨询、物流/重复服务闭环。
- 增加明确的 `DEMO CACHED MODE` / `LIVE QWEN MODE` UI 标识；Demo Mode 使用 mock/固定 SQLite 数据和离线 fallback，不冒充实时 Qwen。
- 新增 `scripts/reset_demo.py`，只清理 `risk_tracking` 覆盖状态，已验证源数据不变。
- 新增 `scripts/demo_preflight.py`，检查 Python、FastAPI/app import、SQLite、前端依赖/build artifact 和 live 配置存在性，不打印 API Key。
- 新增 Windows `scripts/start_demo.ps1`，自动执行 preflight 并启动 mock backend/frontend，输出访问地址。
- 完成 `docs/DEMO_METRICS.md`、`docs/DEMO_SCRIPT.md`、`docs/DELIVERY_CHECKLIST.md`，README 已补充架构、Demo/Live 模式、启动、reset、测试、评估和 FAQ。
- M10 回归：backend tests 25/25 PASS；frontend typecheck PASS；Vite production build PASS；demo preflight READY；demo reset PASS；risk API smoke PASS（risk_total=52、status persistence ok）；workbench sessions/health/risk API HTTP smoke PASS；start_demo.ps1 parse PASS。
- 未发起新的 live Qwen 请求；未进入 M11。

## M11 Simulated Qianniu Plugin Runtime（PASS）

- 本阶段不实现真实千牛 API；目标是满足比赛要求的“模拟千牛客服工作台环境中的插件形态运行”。
- 新增 `frontend/src/pluginRuntime.ts`：定义 `PluginContext`、`PluginActions`、`QianniuHostAdapter`、`SimulatedQianniuAdapter` 和五类宿主事件。
- 新增 `frontend/src/BeautyCopilotPlugin.tsx`：右侧知妍·伴答插件组件，不直接依赖宿主内部 React state。
- `/workbench` 已加入 Host/Plugin 分区、Scenario Controller、消费者下一条消息、Reset Scenario、Host Reply Composer 和插件动作闭环。
- 文档见 `docs/PLUGIN_RUNTIME.md`；真实千牛接入仍为后续可选增强，不因账号或权限缺失阻塞比赛 Demo。
- 回归验证：frontend `npm run typecheck` PASS；Vite production build PASS；backend `python -m unittest discover -s tests -q` 25/25 PASS；`scripts/demo_preflight.py` READY；`scripts/reset_demo.py` PASS。
- 浏览器 click-through（demo cached/mock）：Scenario Controller 发送消息后，消息进入 Host chat 并触发 `MESSAGE_RECEIVED`；AI 分析显示插件身份、intent/emotion/evidence/timeline/risk/actions/suggested reply；Risk Dashboard 详情展示客户、证据、服务轨迹和状态控件。未发起 live Qwen 请求。
- M11 PASS：Host/Plugin 边界、Context/Action 合约、事件生命周期、固定 A/B/C 场景、插件动作到 Reply Composer、风险看板闭环均已具备。真实 Qianniu API 仍为 OPTIONAL M12。

## M11 真实性修订（2026-09-30）

- M11 改为 `Real Scenario Driven Simulated Qianniu Plugin Runtime`：模拟千牛交互环境，不模拟或替换业务数据。
- `/workbench` 的会话列表继续来自现有真实赛题 session API；A/B/C 快捷入口分别加载 `S00082`、`S00002`、`S00075`，而不是创建新客户或替换会话。
- 删除前端加载失败时的“演示客户”与预设消息 fallback，以及风险看板的 mock 风险初始列表；API 不可用时显示明确错误/空态，不伪造业务事实。
- 场景入口只重新加载真实会话，原始订单、工单、风险事件和 Gold evaluation 数据保持不变。Agent、Risk Engine、Evaluation 未修改。
- `docs/PLUGIN_RUNTIME.md` 已补充 Real Scenario Driven Architecture、数据层/适配层/宿主层/插件层/Agent 层边界及未来 Host Adapter 替换方式。
- 离线回归：`npm.cmd run typecheck` PASS；Vite production build PASS；`python -m unittest discover -s tests -q` 25/25 PASS；`python scripts/reset_demo.py` PASS；未发起 live Qwen 请求。
- 本次真实性修订未改变已有浏览器闭环代码路径；本轮重点为移除虚构 fallback，完成 typecheck/build/backend regression，未发起新的 live Qwen evaluation。
- 2026-09-30 启动修复：发现本地 backend/frontend 进程均未监听端口，导致 `http://localhost:5173/` 无法打开；使用 `scripts/start_demo.ps1` 启动 backend，并以受限外部权限运行 `npm.cmd run dev -- --host 127.0.0.1 --port 5173`。验证 `GET /`=200、`GET http://localhost:8000/health`=200，当前为 mock/demo 模式。

## Context-grounded Agent Reply Generation（2026-09-30）

- 修复 mock provider 的固定 suggested reply：现在基于当前会话消息、关联订单、物流/退款/不良反应工单和 risk findings 生成确定性、可解释的客服回复；无事实时明确请求进一步核实，不编造订单或状态。
- `conversation_id` 入口现在会先读取真实会话，再通过关联 buyer context 获取真实订单和工单证据；未改变 Qwen provider、Tool calling、Hybrid Risk 或 Evaluation。
- 插件智能回复建议卡片新增“知妍生成”标识和简短“生成依据”，复制后可在宿主回复编辑器继续修改。
- 离线 API smoke：S00011 回复包含真实物流单号/状态；S00038 回复包含真实退款金额/状态；S00082 回复包含真实不良反应工单号并建议暂停使用与人工升级。
- 测试：backend `python -m unittest discover -s tests -q` 29/29 PASS；frontend typecheck PASS；production build PASS；未发起 live Qwen evaluation。

## Workbench 会话栏展示调整（2026-09-30）

- 左侧标题由“真实赛题会话”调整为“真实会话”。
- 真实会话列表默认显示 8 个；超过 8 个时提供“展开更多/收起”按钮，数据仍来自真实 session API。
- 移除宿主事件摘要文字，事件合约和内部生命周期不变。
- 前端 `npm.cmd run typecheck` PASS；未修改业务数据、Agent、风险引擎或评估流程。

## 前端界面中文化（2026-09-29）

- 为提升插件易操作性，将实际显示页面（`frontend/src/main_m11.tsx`、`frontend/src/BeautyCopilotPlugin.tsx`）中的英文界面文案统一改为中文：顶部品牌/模式标识（演示缓存模式/实时 Qwen 模式）、各分区 eyebrow 标题、按钮（演示场景/发送下一条消费者消息/重置场景/宿主回复编辑器）、宿主事件名、插件分区标题（意图/情绪/证据/订单工单洞察/服务时间线/风险建议动作/建议回复）等。
- 在 `frontend/src/pluginRuntime.ts` 新增统一中文标签映射：风险等级（critical/high/medium/low → 紧急/高危/中风险/低风险）、跟踪状态（open/processing/resolved/ignored → 待跟进/处理中/已解决/已忽略）、风险类别（safety/sentiment/service → 安全/情绪/服务）、五类宿主事件；原始枚举值仍用于接口与数据，未知值回退显示原值。
- 未改动的英文：JSON 证据块的 key、会话编号（如 S00082）、provider 数据值（如 mock-ui）等机器数据；旧入口 `frontend/src/main.tsx` 未被 `index.html` 引用，本轮保持不变。
- 验证：`npm.cmd run typecheck`（tsc --noEmit）PASS；浏览器实测 `/`、`/workbench`、`/risk-dashboard` 三页渲染正常，点击 AI 分析后插件面板各中文分区正确显示，无前端控制台报错（仅有后端 8000 端口未启动的预期网络失败，UI 正常降级 mock）。

## Risk Dashboard 风险详情闭环（2026-09-30）

- 修复 `GET /api/risks/{risk_id}` 与状态更新接口的详情构造调用，返回真实客户、session、订单、工单、风险原因、证据、服务时间线、建议动作和当前状态；未修改 Agent、Hybrid Risk 或 Evaluation。
- 新增 `frontend/src/RiskDashboard.tsx` 风险详情抽屉：风险列表点击“查看详情”后加载详情；支持状态 `pending/processing/resolved`、处理备注保存、列表刷新，以及“查看原始会话”跳转 `/workbench?session_id=...`。
- 后端 HTTP smoke：风险详情返回 `session=S00277`、订单 2 条、工单 1 条、时间线 8 条；状态 `processing` 保存后恢复为原状态，持久化正常。
- 浏览器 click-through（mock/demo）：点击详情展示完整字段；状态切换为处理中并保存，再恢复为待处理；详情抽屉可见“查看原始会话”；浏览器 error logs=0。
- 验证命令：`python -m unittest discover -s tests -q`（30/30 PASS）；`frontend/npm.cmd run typecheck` PASS；`frontend/npm.cmd run build` PASS。
- 本次未发起 live Qwen 请求，`data/raw` 未修改。

### 风险详情布局调整（2026-09-30）

- 风险详情不再作为风险列表之后的独立底部面板；点击“查看详情”后，完整详情直接插入到对应风险条目下方。
- 切换其他风险条目时，旧详情收起，详情随当前选中条目移动，避免列表与详情上下文错位。
- 保留订单/工单上下文、证据、服务时间线、状态持久化和原始会话链接。
- 验证：frontend typecheck PASS；Vite production build PASS；浏览器实际点击首条及其他风险，详情均显示在对应条目之后。

## 产品品牌体系升级（2026-09-30）

- 产品统一命名为 `知妍 AI / Zhiyan AI`，英文产品描述为 `Zhiyan Beauty Copilot`。
- 模块命名统一为：知妍·伴答（Zhiyan Copilot，智能接待辅助插件）、知妍·洞察（Zhiyan Insight Dashboard，风险预警与跟踪中心）、知妍·智核（Zhiyan Intelligence Core，Agent/Tools/Hybrid Risk）。
- 前端用户可见品牌、宿主/插件边界、风险看板标题和智能回复建议文案已完成统一；代码变量、API 字段、数据结构保持不变。
- 新增 `docs/BRAND_GUIDE.md` 与 `docs/PRODUCT_ARCHITECTURE.md`，并更新 README、Demo Script、Plugin Runtime 和 Skill references。
- 本轮未修改 Agent、Qwen 调用、Tools、Hybrid Risk、Evaluation 或原始比赛数据。
- 验证：`frontend/npm.cmd run typecheck` PASS；`frontend/npm.cmd run build` PASS；`python -m unittest discover -s tests -q` 30/30 PASS；浏览器 `/workbench` 与 `/risk-dashboard` 已显示知妍 AI、知妍·伴答、知妍·洞察品牌体系。

## M12-P0 知妍·伴答核心 Copilot 能力升级（2026-10-01）

- 保留现有 Qwen provider、业务 Tools、Hybrid Risk、Evaluation、Demo cached mode 和 Live Qwen mode；未改变品牌、风险算法、数据结构或评估数据。
- `BeautyAgent` 现在返回 UI-safe workflow trace：客户需求、工具核查步骤、已获得事实摘要、风险摘要和回复依据；不返回 raw tool payload。
- 会话入口会显式核查历史会话、客户/订单上下文和相关服务工单，回复生成继续使用真实物流、退款、不良反应和工单事实；缺少事实时明确要求进一步核实。
- 知妍·伴答新增“客户洞察 / 信息核查 / 关键依据 / 风险判断 / 智能回复建议”展示；分析中显示“知妍正在分析”和简洁核查步骤。
- 关键依据已从 raw JSON 改为中文摘要（订单数、工单号、命中信号等），插件不展示原始 Tool payload。
- 新增离线测试覆盖：workflow trace、物流事实回复、退款事实回复、不良反应安抚与人工升级回复；未发起大规模 Qwen evaluation。
- 验证：`python -m unittest discover -s tests -q` 33/33 PASS；frontend `npm.cmd run typecheck` PASS；Vite production build PASS；mock API S00011 返回真实物流单号与状态；浏览器 smoke 显示信息核查步骤和智能回复建议。

## M13-P1 企业级工作台体验升级（2026-10-01）

- 保留模拟千牛 Host + 知妍·伴答 Plugin 边界、真实赛题会话、Agent、Hybrid Risk、Dashboard 和 Demo cached/live 模式；未修改数据结构、风险算法或 Evaluation。
- `/workbench` 左侧真实会话列表继续显示 8 条并支持展开，新增服务状态与风险等级标识；中间 Host 新增客户洞察卡（客户、消费等级、历史订单/服务、情绪、风险）及订单/商品上下文卡。
- 知妍·伴答新增“知妍工作流”四步可视化：理解需求、查询信息、分析风险、生成回复，明确 waiting/running/completed 状态；整体 UI 收敛为企业 SaaS 卡片层级，减少渐变和调试感。
- `/risk-dashboard` 真实风险列表、详情与 Workbench 原始会话闭环保持可用；未发起新的 live Qwen 请求。
- 验证：backend `python -m unittest discover -s tests -q` 33/33 PASS；frontend `npm.cmd run typecheck` PASS；frontend `npm.cmd run build` PASS（Vite 生产构建成功）；浏览器 mock click-through 验证 `/workbench` 客户洞察、订单上下文、插件工作流和真实工具核查展示，`/risk-dashboard` 风险列表与详情加载正常。
- API smoke：更新后的 `/api/workbench/sessions` 在 mock backend 返回真实会话的 `status` 与 `risk_level`（例如 S00362=medium），未读取或输出任何密钥。

## M15 知妍 AI 品牌形象与 Mascot UI Integration（2026-10-02）

- 新增统一品牌资产 `Logo.png`，复制至 `frontend/public/Logo.png`，并新增可复用 `frontend/src/components/brand/Brand.tsx`：`BrandIcon`、`ZhiyanMascot`、`AgentStatusMascot`。
- `/workbench` Header、知妍·伴答插件标题、空状态、分析状态和智能回复建议均使用知妍 Mascot；空状态提供“知妍已准备好”与开始分析引导，分析中使用真实 loading 生命周期，保留 LIVE/DEMO 模式标识。
- `/risk-dashboard` 风险详情增加知妍风险分析与品牌关键依据标识；Host + Plugin 边界保持不变，mascot 未覆盖客户消息区域。
- 新增 `docs/BRAND_UI_GUIDE.md`，定义品牌色、Icon/Mascot 尺寸、状态动画与使用边界。
- 未修改 Qwen provider、Tool calling、Hybrid Risk、数据集或评估流程；未发起新的 Agent evaluation。
- 验证：backend `python -m unittest discover -s tests -q` 33/33 PASS；frontend `npm.cmd run typecheck` PASS；Vite production build PASS；浏览器 smoke 验证 `/workbench` Header/插件/空状态/工作流/回复品牌和 `/risk-dashboard` 风险详情品牌一致，未见页面级运行错误。

## M15-P1 品牌 UI 微调（2026-10-02）

- 替换无背景图标：用 `Logo（无背景）.png` 覆盖 `frontend/public/LogoMascot.png`（透明背景、白团子主体），删除 `make_logo_mascot.py` 与临时探针脚本。
- 移除 `/workbench` Header 副标题"面向美妆客服场景的智能接待与风险洞察 Copilot"（仅保留中英文标题）。
- 移除知妍·伴答空状态大图标（`ZhiyanMascot` 96px），仅保留标题与操作列表。
- 移除风险详情"关键依据"前的 Logo 图标，修正 `ZHiyan COPILOT` 为 `ZHIYAN COPILOT`。
- 删除建议回复卡片底部的"服务提供方 / 耗时"元信息行。
- 验证：frontend `npm.cmd run build` PASS（TypeScript 编译 + Vite 生产构建均通过）；未修改后端、Agent 或评估逻辑。

## Recovery / Integrity Check（2026-10-02）

- 按只读模式检查 SQLite、原始 Excel、generated data、配置、Git 和备份线索；未执行 reset_demo、seed、import 或任何数据库写入。
- `data/beauty_cs_agent.sqlite3` 存在，`PRAGMA integrity_check=ok`；核心记录与导入摘要一致：chat_messages 998、orders 113、工单表合计 80。
- 原始 Excel SHA-256 与 `data/import_summary.json` 一致；未发现可恢复的数据库 backup/previous/WAL 副本。数据库未纳入 Git，无法从 Git 直接恢复 SQLite 版本。
- 检查时本地 API 端口不可连接，且数据库路径为相对路径 `data/beauty_cs_agent.sqlite3`；当前最可能是服务未启动或启动工作目录不正确，而不是数据删除。
- 诊断报告见 `docs/DATA_RECOVERY_REPORT.md`。未自动恢复，等待确认。
- 后续验证已从仓库根目录使用 `.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000` 恢复服务；实际解析数据库为 `E:\beauty-cs-agent\data\beauty_cs_agent.sqlite3`。`/health`=200、工作台会话 total=100、风险 total=52；S00082 返回 10 条消息/1 订单/1 工单，客户摘要与风险详情均可读取真实数据。结论：无需修改路径或数据库，原问题是 API 未监听或启动工作目录不正确。

## Risk Detail Context Navigation（2026-10-02）

- 知妍·伴答的“打开风险详情”现在携带 `risk_id`、`session_id` 和可用 `order_id`，优先跳转 `/risk-dashboard?risk_id=...`；无 risk_id 时按当前客户关联风险查找，找不到则显示“当前会话暂无已生成风险事件”，不跳转总览。
- `/risk-dashboard` 读取 query 参数后自动加载并展开对应风险详情；详情保留客户、会话、订单/工单、风险原因、关键依据、服务轨迹、处理建议和状态，并提供“返回原始会话”。独立“打开知妍·洞察”入口仍跳转总览。
- 后端建议结果增加导航元数据 `risk_id/risk_ids`，不改变 Agent、Hybrid Risk 或 Evaluation；多风险按当前模型风险等级及风险等级排序选择优先事件。
- 浏览器 click-through：S00082 → 分析 → 打开风险详情，URL 包含 `risk_id=方b**:adverse_reaction`、`session_id=S00082`、订单号；风险详情自动展开并显示真实订单/工单/轨迹；点击“返回原始会话”回到 `/workbench?session_id=S00082`。
- 验证：backend 33/33 PASS；frontend typecheck PASS；Vite build PASS；未发起 live Qwen evaluation。

## M16 知妍·伴答 Quick Action Agent 重构（2026-10-02）

- 从当前 998 条聊天及关联订单/工单字段提炼客服行动类型，新增 `docs/CUSTOMER_SERVICE_ACTION_CATALOG.md` 和 `docs/ZHIYAN_COPILOT_INTERACTION.md`。当前实现 10 个可执行 Action，均绑定真实 SQLite 来源；不存在生产 API、直播后台、批次追溯或预计送达时间时不展示伪按钮。
- 新增 `app/action_registry.py` 作为 Action/Tool allowlist；`BusinessTools` 增加订单、物流、退款、打款、退货、换货、售后工单、不良反应、历史沟通和历史承诺的最小结构化查询投影。所有执行请求绑定 `session_id`，NOT_FOUND 明确返回进一步核实。
- 新增 `/api/workbench/{session_id}/actions`、`POST /api/copilot/actions/{action_id}`、`POST /api/copilot/chat`。快捷按钮直接执行真实业务 Tool，Agent Chat 只展示简洁结果和数据来源，不展示 raw payload。
- 右侧知妍·伴答已改为“客户洞察 → 知妍建议行动 → 知妍 Agent → 知妍生成建议回复”；删除“知妍工作流”“信息核查”独立大卡片和中央聊天区“知妍分析当前会话”按钮。会话切换后插件清空短对话并重新加载 Action。
- 浏览器 mock click-through：真实会话 S00362 点击“查看退款状态”返回待审核退款记录 HV8045912170；真实会话 S00082 点击“查看不良反应记录”返回待处理工单 BLFY70604980；两条结果的 `session_id` 和数据来源分别隔离，无串线。
- 新增 `tests/test_action_registry.py`；backend `37/37 PASS`，frontend typecheck PASS，Vite production build PASS；未发起新的 live Qwen evaluation，未修改原始数据、Hybrid Risk 或 Evaluation。

### Workbench Host 边界微调（2026-10-04）

- 移除中部模拟千牛 Host 聊天区上方的“客户洞察”和“订单与商品上下文”卡片；中部现在只保留会话抬头、消费者/客服消息和回复编辑器。
- 客户洞察与建议行动继续只在右侧知妍·伴答插件提供，避免 Host 与 Plugin 的信息职责混淆。
- 验证：frontend `npm.cmd run typecheck` PASS；Vite production build PASS；浏览器 `/workbench?session_id=S00362` smoke 确认中部无上述卡片，右侧插件仍展示客户洞察与建议行动。
- 订单商品信息已移入右侧知妍·伴答，并统一命名为“订单商品”；浏览器验证右侧展示真实商品“【预售】测试修护精华双支装30ml*2”和订单状态，中部仍不显示该卡片。

### 知妍·伴答 UI 微调（2026-10-04）

- 删除建议行动下方与客户洞察重复的“风险：xx”标签；同步移除 `.risk-compact` 顶部分隔横线及配套 padding。
- 修复客户洞察三个方框内因 `.panel label` 全局 margin 导致的顶部空行（`.insight-grid label{margin:0}`）。
- 知妍 Agent 对话改为左右气泡布局：客服靠右深紫气泡、知妍靠左浅紫气泡，消息不再上下整行堆叠。
- 移除 Agent 回复末尾的“以上信息来自当前比赛实例数据。/来自 chat_messages”等来源声明（`app/action_registry.py`），并删除前端气泡中的“数据来源：{source}”行；接口字段保留不变。
- 验证：`python -m pytest tests/test_action_registry.py -q` 4 passed；frontend TS diagnostics 无错误。

### 访问方式永久修复：单进程托管 + 一键启动（2026-10-05）

- 根因：前端 Vite（5173）是独立手工进程，重启/进程回收后不自启（后端 8000 常在跑），导致反复出现 5173 打不开。
- `app/api.py` 新增 SPA 托管：`frontend/dist` 存在时，FastAPI 在所有 API 路由之后注册 `/{full_path:path}` 兜底——静态文件直接返回，其余路径回退 `index.html`，`api/*` 未命中返回 404（不回退页面）。
- `frontend/vite.config.ts` 固定 `host=127.0.0.1`、`port=5173`、`strictPort`，杜绝端口静默漂移到 5174。
- 新增双击启动脚本 `scripts/start_zhiyan.cmd`：检测 8000 未监听时以 mock 模式启动 uvicorn，等待 `/health` 后自动打开 `http://localhost:8000/workbench`；无需 Node/Vite 常驻。
- 统一访问入口为 **http://localhost:8000/workbench**（5173 仅开发时使用，`npm run dev`）；前端改动后需重新 `npm run build` 才会在 8000 生效。
- 验证：frontend build PASS；backend `python -m unittest discover -s tests -q` 37/37 PASS；HTTP smoke：`/workbench` 200、`/risk-dashboard` SPA 200、assets 200、`/api/workbench/sessions` total=100、未知 api 404；浏览器实测页面/会话切换/插件加载正常，console error=0。

## 12-Factor Agent 差距评估（2026-10-09）

依据仓库根目录 `12-factors-agent.docx`（Dex Horthy《12-Factor Agents》中文演绎版，共 12 条原则）对当前架构逐条对照。注意：原文交叉引用编号在文档中存在错位，以原则内容为准。

### 已符合项

- **原则 1/2（组织规划与工具调用、工具执行器）**：`BusinessTools` 提供工具定义，`action_registry` 承担注册表 + `execute_action` 执行器，Agent 输出结构化动作意图——"思考/行动分离"模式已落地。
- **原则 12（无状态归约器，部分）**：FastAPI 无状态服务，业务状态统一外部化到 SQLite（`data/beauty_cs_agent.sqlite3`）。
- **原则 11（从任何地方触发，部分）**：知妍·伴答以插件形式嵌入千牛工作台面板（宿主触发）；HTTP API 可独立调用。

### 差距项（候选 backlog）

| # | 原则 | 差距 | 建议动作 | 优先级 |
|---|------|------|---------|--------|
| G1 | 原则 4 拥有提示词 | ~~系统提示词硬编码在 `app/qwen_agent.py`~~ **已落地（2026-10-09）**，见下方 G1 落地记录 | 已完成 | ✅ |
| G2 | 原则 5 上下文评估与仲裁 | ~~长会话仅按轮次拼接历史，无重要性分级~~ **已落地（2026-10-09）**，见下方 G2 落地记录 | 已完成 | ✅ |
| G3 | 原则 6 错误压缩入上下文 | ~~工具执行失败时错误未结构化回馈给 Agent 自纠~~ **已落地（2026-10-09）**，见下方 G3 落地记录 | 已完成 | ✅ |
| G4 | 原则 7 统一执行/业务状态 | ~~多步执行步骤状态未统一持久化~~ **已落地（2026-10-09）**，见下方 G4 落地记录 | 已完成 | ✅ |
| G5 | 配置外置化（原则 3 相关基础设施） | ~~配置散落在代码 env 读取与启动脚本注入，无统一 .env 加载；`.env.example` 曾混入真实密钥~~ **已落地（2026-10-09）**，见下方 G5 落地记录 | 已完成 | ✅ |
| G5b | 原则 3 人机协同工具化（原 G5） | ~~人工介入（客服编辑回复）是前端自由文本，未建模为结构化"人类工具调用"，审计链不完整~~ **已落地（2026-10-09）**，见下方 G5b 落地记录 | 已完成 | ✅ |
| G6 | 原则 8 任务生命周期 API | 无任务级 pause/resume/cancel 端点（当前均为同步短请求） | 比赛演示无需长任务，可暂缓；仅在做异步长任务时补 | 低 |
| G7 | 原则 9 显式状态机 | 控制流由 mock 分支与 LLM 隐式决策混合，未用显式 FSM 描述 | 可为 Quick Action 流程补充显式状态文档（不必引入框架） | 低 |
| G8 | 原则 10 小而专注 Agent | 单体 `BeautyAgent` 承担意图/回复/风险多职责，比赛规模可接受 | 保持现状；扩展新业务域时再按 DDD 拆分 | 低（暂不动） |

### G1 落地记录（2026-10-09）

- 新增 `app/prompts/` 目录，三个提示词模板外置（内容与原硬编码逐字一致，行为零变化）：
  - `stage_a_tools.txt`：阶段 A 工具调用系统提示词；
  - `final_synthesis.txt`：最终合成阶段提示词（含 `{schema_contract}` 占位符）；
  - `json_repair.txt`：JSON 修复提示词（含 `{schema_contract}` 占位符）。
- `app/qwen_agent.py` 新增 `load_prompt(name, **values)`：读取模板并替换 `{placeholder}`，首次读取后缓存；占位符替换用 `str.replace` 而非 `str.format`，避免模板中字面花括号冲突。
- 三处调用点（`run()` 内 system / synthesis_system / repair_system）改为 `load_prompt(...)`。mock 模式不经过提示词路径，演示行为不受影响；仅 Live Qwen 模式生效。
- 新增守护测试 `test_prompts_are_externalized_and_placeholder_replaced`（tests/test_qwen_agent.py）：校验模板存在、非空、占位符被替换、关键措辞保留。
- 验证：`python -m unittest discover -s tests -q` 38/38 PASS。
- 后续迭代提示词时直接改 `app/prompts/*.txt` 并提交，代码零改动；如需回滚 `git revert` 对应提交即可。

### G3 落地记录（2026-10-09）

- 新增 `app/error_compactor.py`（无内部依赖，供 qwen_agent 与 action_registry 共用）：`compact_tool_error(tool_name, exc)` 把异常提炼为紧凑 JSON `{error_summary, error_type, message, offending_parameter?, suggestion}`——message 取首行并截断 200 字符，None 字段省略以省 token；规则化 suggestion：意外参数→改用 schema 参数名、缺参→补齐、KeyError→数据缺失不要编造、JSONDecodeError→按 schema 重试、兜底→如实告知会进一步核实。
- `app/qwen_agent.py` 工具循环失败分支：原先回注无信息量的 `{"error": "tool failed"}`，现改为回注压缩错误 JSON，LLM 可据此改参自纠；`args` 初始化移入 try 前，修复解析失败时未绑定问题；`errors` 审计列表保留 `tool_error:<name>:<Type>`。
- `app/action_registry.py`：`execute_action` 工具异常时不再向上抛裸异常（原会 500），返回 `status="ERROR"` + 压缩错误载荷的完整结果；`format_action_result` 新增 ERROR 分支，用户侧文案诚实为"业务查询服务暂时异常…"（区别于 NOT_FOUND 的"未找到相关记录"）。API 契约不变（仍 200 + status 字段），KeyError 未知 action 仍按原样 404。
- 新增 `tests/test_error_compactor.py`（6 例：意外参数/缺参/KeyError/JSON 解析/兜底压缩/长消息截断）；`tests/test_action_registry.py` 补 2 例（ERROR 载荷结构、ERROR 文案）。
- 验证：`python -m unittest discover -s tests -q` 46/46 PASS。
- 生效范围：Live Qwen 模式的工具自纠链路与 Quick Action 执行兜底；mock 演示路径不受影响。

### 启动脚本修复：双击 start_zhiyan.cmd 无效（2026-10-09）

- 症状：双击 `scripts/start_zhiyan.cmd` 不打开网页，`http://localhost:8000/workbench` 不可达。
- 根因（字节级证据）：脚本文件为 **LF（Unix）换行**（start_zhiyan.cmd 44 处 bare-LF、CRLF=0）+ UTF-8 中文 + `chcp 65001` + `goto` 标签 + `if (...)` 多行块。cmd.exe 对 LF-only 批处理的标签定位与块解析不可靠，双击后脚本解析错乱提前终止——服务未启动、浏览器未打开。后端本身无问题（直接以 venv python 启动 uvicorn 后 health/workbench 均 200）。
- 修复：`scripts/start_zhiyan.cmd` 与新增 `scripts/run_service.cmd` 以 **CRLF + 纯 ASCII** 重写（移除 chcp 与中文输出，消除编码/码页隐患）：
  - 启动器：netstat 探测端口（不依赖 curl）→ 未监听则 `start /MIN` 最小化窗口运行 run_service.cmd → 轮询就绪后 `start` 打开浏览器；超时（约 60s）时自动打印服务日志并 pause。
  - run_service.cmd：设置 mock 环境变量，uvicorn 输出重定向到 `logs/zhiyan_service.log`——服务崩溃不再随窗口消失，失败可查。
- 限制：本开发沙箱会拦截所有 Start-Process 生成的窗口进程（连最小 ASCII 测试 cmd 都不执行），无法在沙箱内端到端验证双击路径；已验证字节格式（CRLF=43/9、bare-LF=0、non-ASCII=0）、脚本结构与后端服务可用性，最终以用户双击实测为准。若再失败，窗口会直接显示错误日志。
- 修复后服务已由会话后台进程拉起，health 200 / workbench 200。

### G2 落地记录（2026-10-09）

- 新增 `app/context_arbiter.py`（规则版仲裁器，无内部依赖），替代 `suggest()` 中 `[-6:]`/`[:3]` 的 FIFO 一刀切：
  - **消息分级** `_score`：最新消息=5；核心诉求关键词（退款/退货/过敏/赔偿/发货等 24 项）=5；业务实体（订单号/单号/金额正则）或关联记录=4；寒暄短消息（≤12 字且命中寒暄词）=1；其余=3。
  - **两阶段预算**：阶段 A 完整窗口 ≤ max_messages(6)，最新消息 + 必须保留项优先、背景消息按新旧补位；阶段 B 压缩区 ≤ max_entries(12)，未进窗口的必须保留项做规则摘要（截断 80 字 + 附加"关键实体：…"，标记 `text_truncated`），其余丢弃。原始核心诉求永不因窗口不足被挤出。
  - **订单排序** `arbitrate_orders`：入参指定订单 > 会话内被提及订单 > 其余，超出 3 条丢弃低相关项。
  - 仲裁统计 `context_arbitration: {messages: {total/kept/compressed/dropped}, orders: {…}}` 随 request_context 进入 workflow trace，可观测。
- `app/qwen_agent.py` `suggest()` 接线：`recent_messages`/`orders` 改由仲裁器产出；风险引擎 `assess_context` 仍吃全量 context 不受影响；mock 模式兼容（recent_messages 结构不变）。
- 新增 `tests/test_context_arbiter.py` 8 例：短会话直通、最新消息必留、核心诉求不被挤出（关键回归）、寒暄先丢、实体溢出压缩不丢弃、顺序保持、订单排序与直通。
- 验证：`python -m unittest discover -s tests -q` 54/54 PASS。
- 已知限制：摘要压缩为规则版（截断 + 实体保留），未用 LLM 摘要；`max_messages=6` 与原 token 预算持平，压缩区最多 12 条有硬顶。

### G4 落地记录（2026-10-09）

- 新增 `app/task_state.py`（原则 7）：`agent_tasks` 表（task_id 主键 + execution_state + business_state_json + error + run_id + 时间戳），与业务数据同库持久化；连接用显式关闭的 contextmanager（`with conn:` 只管事务不释放 Windows 文件锁）。
- 执行状态机：`started → context_ready → synthesis_done → completed / failed`。business_state 增量合并——started 记录入参、context_ready 记录上下文规模/风险等级/仲裁统计、synthesis_done 记录 provider/用量/工具调用、completed 记录结果摘要，failed 记录错误（截断 300 字符）并继续向上抛出（API 行为不变）。
- `qwen_agent.suggest()` 拆为包装层（task 生命周期管理）+ `_suggest_inner`（原执行体，内嵌 2 处状态推进）；`AgentResult` 新增 `task_id` 字段（带默认值，不破坏既有位置参数构造），经 `dict(result.__dict__)` 自动透出给前端。
- 新增观测端点：`GET /api/agent/tasks`（列表，最新在前，limit 上限 100）、`GET /api/agent/tasks/{task_id}`（单任务详情，404 兜底）。
- 新增 `tests/test_task_state.py` 6 例：状态合并回读、failed 落库、非法状态拒绝、缺失任务 None、列表排序限数、suggest 全生命周期集成断言（mock 路径四个阶段业务状态齐全）。
- 验证：`python -m unittest discover -s tests -q` 60/60 PASS；重启服务后实测 `GET /api/agent/tasks?limit=2` 返回 completed 任务（risk_level/provider 字段齐全）。
- 已知限制：同步短请求场景，暂不做断点续传执行（重启后轨迹可查但不自动恢复）；状态推进点在 suggest 单入口内，Quick Action 路径未纳入（其为确定性单步调用，agent_runs 已覆盖）。

### G5 落地记录：配置外置化（2026-10-09）

- 新增 `app/config.py`（无第三方依赖的微型 .env 加载器）：`parse_env` 解析 KEY=VALUE（忽略空行/# 注释、剥离首尾空白与成对引号）；`load_env` 把仓库根目录 `.env` 中进程环境尚不存在的键注入 `os.environ`，**已存在的真实环境变量优先**（启动脚本注入的 `AGENT_PROVIDER=mock` 不被覆盖）。
- `app/qwen_agent.py` 与 `app/api.py` 在模块导入时先 `load_env()`，再读取任何配置（api.py 的 `DB_PATH` 与 QwenProvider 的 12 项 env 读取全部经由 .env 可配置）。
- `.env.example` 修复安全问题并补全：此前该文件混入了真实 QWEN_API_KEY（违反占位符规则），已替换为 `sk-your-key-here`；补全 QWEN_MOCK、QWEN_ENABLE_THINKING、QWEN_DEBUG_DIR 等全部键并附中文注释。`.env` 真实值未改动。
- 优先级语义：真实环境变量 > .env > 代码默认值。`scripts/run_service.cmd` 注入的 mock 强制继续生效；手动裸启 uvicorn 时将采用 .env 的 `AGENT_PROVIDER=qwen`（.env 即唯一配置源）。
- 新增 `tests/test_config.py` 4 例：解析（引号/注释/空白）、真实 env 优先不被覆盖、缺失文件 no-op、.env.example 占位符与键全覆盖守护。
- 验证：`python -m unittest discover -s tests -q` 68/68 PASS；重启后 `/health` provider=mock（脚本注入优先级正确）。

### G5b 落地记录：原则 3 人机协同工具化（2026-10-09）

- 新增 `app/human_feedback.py`：`human_feedback` 表（feedback_id 主键、conversation_id、original_reply、edited_reply、created_at）与业务数据同库持久化，连接用显式关闭的 contextmanager（Windows 文件锁随关闭释放）；`record_feedback` 校验非空并生成 `fb_` 前缀 ID，`list_feedback` 支持按会话过滤/限量（供审计查询）。
- 新增 `POST /api/copilot/feedback`：校验会话存在（404）与回复非空（400），落库后返回 `{feedback_id, conversation_id, recorded}`。
- 前端接线（`frontend/src/main_m11.tsx`）：插件「复制到回复框」时记录本次插入的建议文本（lastInserted，切换会话时清空）；点击「发送给消费者」时，若本次会话插入过 AI 建议，自动以 `{conversation_id, original_reply: 插入的建议, edited_reply: 最终文本}` 调用反馈端点（失败静默，不阻断模拟发送）；未采纳建议的普通发送不产生记录。
- 审计链闭合：AI 建议（agent_runs/agent_tasks 已有）→ 人工修订（human_feedback）→ 发送；未经编辑直接采纳也会留痕（可计算采纳率）。
- 新增 `tests/test_human_feedback.py` 4 例：落库回读、按会话过滤与限量、空回复拒绝、跨连接持久化。
- 验证：unittest 68/68 PASS；frontend typecheck + Vite production build PASS；重启服务后实测 POST /api/copilot/feedback 返回 feedback_id（S00082，内容带 [smoke] 标记，保留作功能演示数据）。
- 已知限制：反馈为 best-effort 上报（网络失败静默，不做重试）；快捷行动结果经复制后同样被记录为"原始建议"；暂无读取端点（`list_feedback` 模块级可用，UI 展示按需再加）。

### Git 历史安全重写（2026-10-10）

- 背景：`.env.example` 曾在历史提交（已推送到 GitHub）中混入真实 QWEN_API_KEY，违反占位符规则；G5 落地时工作区文件已改回占位符，本轮继续清除历史。
- 操作：`git stash` 暂存未提交工作 → `git bundle` 备份至 Temp → `git filter-repo --replace-text` 将历史中的真实 Key 替换为 `sk-your-key-here` → `git stash pop` 恢复工作区（改动完整保留）。
- 额外发现：Trae/Codex 编辑器快照引用 `refs/codex/turn-diffs/checkpoints/...` 持有含 Key 的旧 `.env.example` blob，filter-repo 不会重写此类工具快照；已删除该引用并 `repack -a -d -f` + `prune --expire=now`，旧 blob 确认从对象库消失（122→120 对象）。
- 远端：force push 覆盖 `origin/master`（d923243 → 8af1484），GitHub 上的旧历史已被替换。提交信息、作者、日期保留，工作区 33 项改动不变。
- 建议：尽管历史已清除，GitHub 可能缓存旧提交视图（fork/PR 引用不可控），**仍建议到阿里云控制台轮换该 Key**；新 Key 只放 `.env`。Temp 中的重写前备份 bundle 含旧 Key，确认无误后应删除。

### 结论

G1–G5（含 G5b 人机协同）已完成，剩余 G6–G8 优先级均为低（演示阶段不动）；若后续迭代，建议顺序 G7。
