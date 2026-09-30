# 知妍 AI 3–5 分钟比赛演示脚本

开场统一表述：“这是知妍 AI 的智能接待插件——知妍·伴答；这是知妍 AI 的风险洞察中心——知妍·洞察。”

Use `scripts/start_demo.ps1` and open `/workbench`. Keep the header mode badge visible.

1. **痛点（20 秒）** — 点击 `/workbench`，说明客服需要在聊天、订单、工单和历史承诺之间快速判断，而风险常常在跨记录信息里。
2. **消费者进线（30 秒）** — 选择场景 A 的会话 `S00082`，展示左侧会话列表和中间按时间排列的买家/客服消息。
3. **知妍·伴答理解（30 秒）** — 点击“知妍 AI 分析当前会话”，等待 loading 完成，说明当前是 `DEMO CACHED MODE` 或明确的 `LIVE QWEN MODE`。
4. **业务信息查询（35 秒）** — 在右侧知妍·伴答展示 intent、emotion、订单/工单、关键依据；说明插件只通过白名单业务 Tools 查询必要事实。
5. **服务轨迹（25 秒）** — 展示 timeline，指出历史承诺、不良反应或未闭环线索如何被串起来。
6. **风险与回复（35 秒）** — 展示风险、处理建议和智能回复建议，强调高风险场景需人工接管，不做医疗诊断。
7. **进入看板（30 秒）** — 点击“知妍·洞察”，按等级筛选，找到同一客户的风险事件并打开详情。
8. **风险闭环（30 秒）** — 展示 evidence、risk reasons、service timeline，将跟踪状态改为 `processing` 并保存；刷新后确认状态仍在。
9. **普通场景对照（25 秒）** — 回到 `/workbench` 选择 `S00002`，说明普通赠品/套装咨询也能得到简洁回复，不会被一律升级。
10. **技术亮点（20 秒）** — 总结知妍·智核中的 Qwen + business Tools + structured output + Hybrid Risk + token/context optimization；说明真实千牛生产接入是可选增强，不是本 Demo 前提。
