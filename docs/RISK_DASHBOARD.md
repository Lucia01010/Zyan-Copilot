# M6 — 风险预警跟踪看板

M6 已开始，当前包含风险列表、等级筛选、详情证据和状态跟踪。

## API

- `GET /api/risks?level=&status=`：按风险等级和跟踪状态筛选。
- `GET /api/risks/{id}`：返回风险原因、证据、建议动作和当前状态。
- `PATCH /api/risks/{id}`：更新 `open`、`processing`、`resolved` 或 `ignored` 状态及处理备注。

跟踪状态写入 SQLite `risk_tracking`，风险规则重新计算时保留人工跟踪状态和备注。

## 前端

`/risk-dashboard` 支持等级筛选、风险行选择、详情面板、证据 JSON、建议动作、状态选择、处理备注和保存跟踪状态。API 不可用时保留 mock 风险样例。
