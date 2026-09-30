"""Deterministic hybrid risk policy; preserves model and rule outputs separately."""
from __future__ import annotations

from typing import Any

from app.risk_engine import LEVEL_ORDER


def _max_level(*levels: str | None) -> str | None:
    values = [str(level).lower() for level in levels if level and str(level).lower() in LEVEL_ORDER]
    return max(values, key=lambda level: LEVEL_ORDER[level]) if values else None


def hybrid_risk(context: dict[str, Any], model_risk: str | None, rule_risk: str | None, findings: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join(str(m.get("message_text") or m.get("chat_content") or "") for m in context.get("messages", []))
    floors: list[tuple[str, str, str]] = []
    if any(f.get("rule_id") == "adverse_reaction" for f in findings):
        floors.append(("high", "hard_adverse_reaction", "明确不良反应证据，风险至少 HIGH。"))
    if any(f.get("rule_id") == "urgent_complaint" for f in findings) or any(term in text for term in ("12315", "监管", "举报", "曝光")):
        floors.append(("high", "hard_complaint_escalation", "明确投诉或监管升级证据，风险至少 HIGH。"))
    promise_terms = ("承诺", "答应", "回访")
    if any(term in text for term in promise_terms) and context.get("messages"):
        floors.append(("medium", "hard_unfulfilled_promise_candidate", "存在历史承诺/回访线索，至少 MEDIUM，需人工确认是否已履行。"))
    rule_floor = _max_level(*(floor[0] for floor in floors))
    model = (model_risk or "").lower()
    final = _max_level(model, rule_floor) or (str(rule_risk).lower() if rule_risk and str(rule_risk).lower() in LEVEL_ORDER else "low")
    return {"model_risk": model_risk, "rule_risk": rule_risk, "rule_floor": rule_floor, "final_risk": final, "reasons": [floor[2] for floor in floors], "applied_rules": [floor[1] for floor in floors]}
