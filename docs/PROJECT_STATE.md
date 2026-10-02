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
