# 人工 Gold Set 标注指南

## 使用方式

先生成候选：

```powershell
& '.venv\Scripts\python.exe' scripts/build_manual_gold_candidates.py
```

逐条查看 CSV 中的聊天、订单、工单和 Rules 证据。可以使用 CLI reviewer：

```powershell
& '.venv\Scripts\python.exe' scripts/review_manual_gold.py
```

只有人工填写完整并标记为 `REVIEWED` 的行才会导出到 `data/generated/evaluation/manual_gold.jsonl`。候选 CSV 中所有 `human_*` 字段初始为空，系统不会替人工决定。

## Intent

优先沿用 `source_scene_major` 和 `source_scene_minor`。如果完整聊天、订单、工单显示场景不同，可以修正，并在 review notes 写明理由。不要根据模型输出填写 intent。

## Risk

只能选择：`LOW`、`MEDIUM`、`HIGH`、`CRITICAL`。

- `LOW`：普通产品/物流/订单咨询，问题清楚，没有历史承诺、重复未解决服务或安全/投诉信号。
- `MEDIUM`：已经影响服务体验，或存在明确历史承诺未履行、重复沟通、重要信息缺失等，需要跟进但暂未达到严重升级。语气平静不等于 LOW。
- `HIGH`：明确投诉、平台/监管升级、重复未解决问题、异常退款/售后，或明显情绪升级，需要尽快人工介入。
- `CRITICAL`：明确不良反应、就医/人身安全风险、严重安全事件或紧急监管风险，需要立即人工接管。

判断时先看完整证据，再看当前语气。历史承诺未履行至少考虑 `MEDIUM`；不良反应、就医、严重投诉或监管升级应提高到 `HIGH` 或 `CRITICAL`。如果证据不足，选择较低等级并在理由中写明缺失信息，不要猜测。

## required_tools

填写正确处理至少需要的工具名称，多个用逗号分隔：

`order`、`conversation_history`、`adverse_reaction`、`logistics`、`replacement`、`refund`、`timeline`。

例如：过敏与历史承诺冲突通常需要 `conversation_history,adverse_reaction,timeline`；赠品缺失通常需要 `order,replacement`。只选择确实影响判断的工具。

## 特别案例

Case C（历史承诺/备注未执行）必须保留。不要因为 Rules 或 Qwen 任一方的等级就直接判定正确；如果现有证据无法决定，使用人工判断并在 notes 写明依据。人工 gold set 完成前，不计算正式 intent accuracy、risk accuracy，也不声称 Agent improvement。
