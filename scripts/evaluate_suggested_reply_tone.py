"""Compare suggested_reply tone on five real source conversations.

The baseline function is loaded from HEAD for an offline, no-Qwen comparison.
It never writes customer data or sends a network request.
"""
from __future__ import annotations

import ast
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.business_tools import BusinessTools
from app.context_arbiter import arbitrate_messages, arbitrate_orders
from app.context_engine import ContextEngine
from app.hybrid_risk import hybrid_risk
from app.qwen_agent import QwenProvider, BeautyAgent

DB = ROOT / "data/beauty_cs_agent.sqlite3"
CASE_TERMS = {
    "日常产品咨询": ("怎么用", "如何使用", "功效", "适合", "面膜", "精华"),
    "物流进度查询": ("物流", "快递", "签收", "发货"),
    "退款延迟": ("退款", "退钱", "到账"),
    "消费者投诉": ("投诉", "不满意", "失望"),
    "产品使用后不适": ("刺痛", "发红", "红肿", "过敏", "不适", "瘙痒"),
}
REAL_CASE_IDS = {
    "日常产品咨询": "S00034",
    "物流进度查询": "S00009",
    "退款延迟": "S00005",
    "消费者投诉": "S00064",
    "产品使用后不适": "S00015",
}


def _real_cases() -> dict[str, str]:
    with sqlite3.connect(DB) as conn:
        rows = conn.execute("SELECT conversation_id, message_text FROM chat_messages WHERE conversation_id IS NOT NULL ORDER BY conversation_id, CAST(message_sequence AS INTEGER)").fetchall()
    grouped: dict[str, list[str]] = {}
    for cid, message in rows:
        grouped.setdefault(cid, []).append(str(message or ""))
    chosen = {}
    used: set[str] = set()
    for category, terms in CASE_TERMS.items():
        candidates = [(cid, messages[-1]) for cid, messages in grouped.items() if any(term in messages[-1] for term in terms)]
        candidates = [item for item in candidates if item[0] not in used] or candidates
        if candidates:
            chosen[category] = sorted(candidates, key=lambda x: x[0])[0][0]
            used.add(chosen[category])
    # Prefer a stable, manually checked slice of the source conversations so
    # repeated evaluations compare the same real cases.
    return {category: cid for category, cid in REAL_CASE_IDS.items() if cid in grouped}


def _baseline_function():
    source = subprocess.check_output(["git", "show", "HEAD:app/qwen_agent.py"], cwd=ROOT, text=True, encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "QwenProvider")
    method = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "_mock_suggested_reply")
    namespace = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "baseline", "exec"), namespace)
    return namespace["_mock_suggested_reply"]


def _request_context(conversation_id: str):
    tools = BusinessTools(DB)
    engine = ContextEngine(DB)
    ctx = engine.build(conversation_id=conversation_id)
    compact = tools._project("customer_context", ctx.raw_context)
    recent, _ = arbitrate_messages(compact.get("messages", []), max_messages=6)
    orders, _ = arbitrate_orders(compact.get("orders", []), None, recent, max_orders=3)
    return {"conversation_id": conversation_id, "recent_messages": recent, "orders": orders, "work_orders": compact.get("work_orders", [])[:6]}, ctx.risk or {}


def main() -> None:
    baseline = _baseline_function()
    agent = BeautyAgent(DB, QwenProvider(mock=True))
    rows = []
    for category, conversation_id in _real_cases().items():
        request, risk = _request_context(conversation_id)
        before = baseline(request, risk)
        after = agent.suggest(conversation_id=conversation_id).suggestion
        rows.append({"category": category, "conversation_id": conversation_id, "before": before, "after": after,
                     "checks": {"no_baby_words": not any(x in after for x in ("宝宝", "宝子")),
                                "no_ungrounded_promise": not any(x in after for x in ("保证退款", "一定到账", "明天送达")),
                                "consumer_ready": len(after) <= 300}})
    output = ROOT / "data/generated/evaluation/suggested_reply_tone.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "cases": len(rows), "all_checks_passed": all(all(x["checks"].values()) for x in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
