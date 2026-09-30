# M11 知妍·伴答 Simulated Qianniu Plugin Runtime

## 目的

比赛允许用 Vibe Coding 模拟千牛客服工作台。本项目因此把 `/workbench` 明确拆成模拟宿主和独立插件，验证真实客服流程、Agent 工具调用和风险闭环；真实千牛生产部署仍是可选增强，不是比赛交付前提。

## Real Scenario Driven Architecture

模拟的是千牛工作台交互环境，不是业务数据。数据层始终使用真实赛题导入的会话、订单、工单、风险事件和 Gold evaluation scenarios；不创建虚构客户作为主要展示内容。适配层 `Qianniu Simulator Context Adapter` 把这些真实记录转换为宿主所需上下文，宿主只模拟列表、聊天、订单/工单侧栏和回复编辑器。未来接入真实千牛时，只替换 Host Adapter，业务 Agent、Tools、Hybrid Risk、插件和 Dashboard 保持不变。

## Host / Plugin 边界

左侧会话列表、中间聊天区、订单/商品上下文和回复编辑器属于模拟千牛客服工作台宿主。右侧 `知妍·伴答 / Zhiyan Copilot` 只消费宿主提供的上下文，展示意图、情绪、摘要、关键依据、订单/工单洞察、服务轨迹、风险、处理建议和智能回复建议。

## Plugin Context Contract

前端 `pluginRuntime.ts` 定义 `PluginContext`：`sessionId`、`customer`、`currentMessages`，以及可选的 `currentOrder`、`currentProduct`。插件不读取宿主 React state；宿主通过 context 适配层传值。

## Plugin Action Contract

插件通过 `PluginActions` 请求宿主执行 `insertSuggestedReply(text)`、`requestHumanTakeover()`、`openRiskDetail(riskId?)`。复制建议回复实际写入宿主的 Reply Composer，而不是直接操作聊天组件。

## 生命周期与事件

`SimulatedQianniuAdapter` 提供轻量事件机制：`SESSION_CHANGED`、`MESSAGE_RECEIVED`、`AGENT_ANALYSIS_STARTED`、`AGENT_ANALYSIS_COMPLETED`、`RISK_EVENT_CREATED`。切换真实会话会替换 context 并清理旧分析；`MESSAGE_RECEIVED` 保留为宿主事件合约，未来由真实或模拟宿主在收到数据层新消息时发出，本阶段不向真实会话注入预设文本。

## 知妍·智核与知妍·洞察

宿主仍调用现有 FastAPI `/api/workbench/suggest`，后端能力归入 `知妍·智核 / Zhiyan Intelligence Core`，负责业务 Tools、Qwen/mock provider 和 Hybrid Risk。风险事件由现有后端写入 SQLite，插件的“打开风险详情”进入 `知妍·洞察 /risk-dashboard`，看板负责关键依据、服务轨迹和状态跟踪。

## 场景控制器

工作台内置 M10 的 A/B/C 固定真实案例快捷入口（`S00082` 不良反应/历史服务、`S00002` 赠品缺失/普通售后、`S00075` 物流/重复进线）。选择或加载按钮只请求对应真实会话；重新加载会清理插件状态并再次读取原始会话。不会向会话注入预设消费者文本，也不会在 API 失败时构造“演示客户”。

## 未来适配

当前实现是 `SimulatedQianniuAdapter`。未来可实现同一 `QianniuHostAdapter` 合约的 `RealQianniuAdapter`，替换宿主事件和上下文来源；Agent 后端、风险引擎和插件 UI 无需重写。真实 API、店铺账号和开放平台权限不在本阶段实现。
