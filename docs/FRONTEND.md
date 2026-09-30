# M4 — React 前端

前端位于 `frontend/`，使用 Vite + React + TypeScript。

运行（安装 Node/npm 后）：

```powershell
cd frontend
npm install
npm run dev
```

页面：

- `/workbench`：会话气泡、订单号输入、辅助建议、风险提示、复制和人工接管入口。
- `/risk-dashboard`：按等级筛选风险事件、查看证据/建议动作、跟进入口。

通过 `VITE_API_URL` 配置后端地址。API 不可用时工作台使用离线 mock 建议，看板保留演示风险数据，便于比赛演示和前端开发。
