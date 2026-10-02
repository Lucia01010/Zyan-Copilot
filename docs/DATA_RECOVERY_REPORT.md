# Data Recovery / Integrity Check

检查日期：2026-10-02（Asia/Shanghai）

本次仅执行只读检查：未修改 SQLite、未执行 `reset_demo`、未执行 seed/import、未修改 UI 或原始比赛材料。

## A. 当前数据状态

### SQLite

- 配置路径：`.env` 中为 `data/beauty_cs_agent.sqlite3`。
- 实际文件：`E:/beauty-cs-agent/data/beauty_cs_agent.sqlite3`，约 1.42 MB，存在。
- `PRAGMA integrity_check`：`ok`。
- 当前表及记录数：

| 表 | 记录数 |
| --- | ---: |
| chat_messages | 998 |
| orders | 113 |
| replacement_work_orders | 24 |
| offline_payment_work_orders | 13 |
| logistics_work_orders | 15 |
| adverse_reaction_work_orders | 10 |
| after_sales_return_work_orders | 18 |
| data_description | 18 |
| import_runs | 4 |
| agent_runs | 4936 |
| risk_tracking | 1 |

### 原始与生成文件

- 原始 Excel：`data/raw/赛题 1：数据共情者-业务数据.xlsx`，约 171 KB。
- 原始 Excel SHA-256 与 `data/import_summary.json` 中记录一致：`b5ac027e...7307b7`（报告中不展开敏感内容）。
- `data/import_summary.json` 记录的导入行数与当前核心业务表一致：聊天 998、订单 113、各工单表 10–24 条。
- 生成评估数据仍存在：`m8_dataset.json`、`metrics.json`、人工 Gold CSV 及其排序修复备份。
- 未发现项目内有效的数据库备份副本。

## B. 丢失的数据类型

从磁盘和 SQLite 证据看，未确认真实业务数据被删除。核心会话、订单和工单记录仍在。

如果页面显示空数据，表现更可能是 API 未启动、前端连接到不可用端口，或启动时工作目录导致相对数据库路径解析错误。

## C. 数据是否可恢复

- 当前数据：可直接使用，SQLite 完整性通过。
- 原始数据：可从只读 `data/raw` Excel 重新导入，但本次没有执行导入，避免覆盖现有数据库。
- Git：数据库由 `.gitignore` 忽略，Git 提交中没有可直接恢复的 SQLite 版本；最近提交主要包含代码和原始材料。
- 备份：未发现 `.bak`、previous/backup SQLite 文件；检查时未发现可供恢复的 WAL/SHM 副本。

## D. 原因判断

最可能原因：运行时服务状态或数据库路径上下文异常，而不是数据库文件损坏。

证据：

1. SQLite 文件存在，完整性检查为 `ok`。
2. 表结构和记录数与导入摘要一致。
3. 原始 Excel 哈希与导入摘要一致，原始材料没有变化。
4. `.env` 使用相对路径 `data/beauty_cs_agent.sqlite3`；若从仓库根目录之外启动，可能解析到错误位置。
5. 当前检查时 `127.0.0.1:8000` API 连接不可用，因此页面可能展示空态或数据加载失败。
6. `scripts/start_demo.ps1` 会先运行 preflight，再从仓库根目录启动后端；应优先确认使用了该入口或等价的根目录工作目录。

附带安全风险：检查发现配置样例中存在不应进入仓库的凭证内容。报告不复现该值；这不是本次数据丢失原因，但应在后续恢复确认后立即轮换并从版本控制历史中清理。

## E. 推荐恢复方案（等待确认）

1. 先从仓库根目录启动后端，确认 `GET /health` 返回数据库正常，再检查 `/api/workbench/sessions` 的总数是否为 100。
2. 检查启动进程的当前工作目录和最终解析的 `BEAUTY_DB_PATH`，不要先执行导入或 reset。
3. 若仍为空，再对当前 SQLite 做只读备份副本后，由用户确认是否运行幂等 Excel 导入脚本；本报告未自动执行。
4. 轮换暴露的 API 凭证，并确保 `.env.example` 只保留占位符；此项需要单独确认后处理。

## 结论

当前没有证据证明真实业务数据已丢失；优先结论是“数据仍在，服务或路径未正确连接”。未执行任何自动恢复操作，等待用户确认下一步。

## Follow-up Verification（2026-10-02）

### Backend runtime

- 启动目录：`E:\beauty-cs-agent`（仓库根目录）。
- Python：`E:\beauty-cs-agent\.venv\Scripts\python.exe`，Python 3.11。
- 命令：`.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000`。
- 监听：`127.0.0.1:8000`。
- 运行配置：mock provider，仅用于本地数据/API恢复验证，不发起 Qwen 请求。
- 代码配置 `app.api.DB_PATH`：`data\beauty_cs_agent.sqlite3`。
- 实际解析路径：`E:\beauty-cs-agent\data\beauty_cs_agent.sqlite3`，文件存在。

### API checks

| Endpoint | Result | Evidence |
| --- | --- | --- |
| `/health` | PASS | HTTP 200，database=ok |
| `/api/workbench/sessions` | PASS | total=100，首个会话 S00474 |
| `/api/workbench/sessions/S00082` | PASS | 真实会话 10 条消息、1 个订单、1 个工单 |
| `/api/customers/{buyer}/summary` | PASS | 方b**：10 条消息、1 个订单、1 个工单 |
| `/api/risks` | PASS | total=52 |
| `/api/risks/{risk_id}` | PASS | 周h**：2 个订单、1 个工单、8 条服务轨迹 |

### Endpoint scope note

当前代码没有 `/api/sessions`、`/api/customers`、`/api/orders` 这三个集合路由，访问返回 404；实际前端使用的工作台、客户摘要、风险接口均正常，不应将这些未声明路由误判为数据库丢失。

### Follow-up conclusion

本次确认不是数据库路径错误：从仓库根目录启动时，后端已正确读取原始 SQLite，Workbench 与 Risk Dashboard 所需数据均恢复可读。之前页面空数据的直接原因是 API 服务未监听 8000（或未从仓库根目录启动）。未修改数据库、UI、原始文件，也未执行 reset/import。
