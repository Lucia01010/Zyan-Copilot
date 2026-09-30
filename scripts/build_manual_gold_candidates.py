"""Create a stratified, evidence-first manual gold candidate CSV; never fill human fields."""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.business_tools import BusinessTools
from app.risk_engine import assess_context


FIELDS = [
    "case_id", "session_id", "source_scene_major", "source_scene_minor", "conversation_excerpt",
    "relevant_order_summary", "relevant_ticket_summary", "rule_risk_level", "rule_risk_reasons",
    "human_intent_major", "human_intent_minor", "human_risk_level", "human_risk_reason",
    "human_required_tools", "human_review_notes", "human_review_status",
]


def rows_from_db(db: Path) -> list[dict]:
    tools = BusinessTools(db)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        sessions = conn.execute("SELECT conversation_id, buyer_nickname, GROUP_CONCAT(DISTINCT scene_major) AS major, GROUP_CONCAT(DISTINCT scene_minor) AS minor, COUNT(*) AS n FROM chat_messages WHERE conversation_id IS NOT NULL GROUP BY conversation_id, buyer_nickname ORDER BY conversation_id").fetchall()
        result = []
        for row in sessions:
            context = tools.get_customer_context(row["buyer_nickname"])
            # BusinessTools customer context is newest-first for UI freshness. For review,
            # always use the source conversation's chronological sequence explicitly.
            messages = [dict(x) for x in conn.execute("SELECT * FROM chat_messages WHERE conversation_id = ? ORDER BY CAST(message_sequence AS INTEGER) ASC, _row_number ASC LIMIT 8", (row["conversation_id"],)).fetchall()]
            relevant_orders = [o for o in context["orders"] if str(o.get("conversation_id")) == str(row["conversation_id"])]
            tickets = [w for w in context["work_orders"] if str(w.get("conversation_id")) == str(row["conversation_id"])]
            # Rule stratification uses the same buyer-level context as the product risk API;
            # evidence summaries remain limited to this session's order/tickets/messages.
            risk = assess_context(context)
            text = " ".join(str(m.get("message_text") or m.get("chat_content") or "") for m in messages)
            result.append({"session_id": str(row["conversation_id"]), "buyer": row["buyer_nickname"], "major": row["major"] or "", "minor": row["minor"] or "", "text": text, "messages": messages, "orders": relevant_orders, "tickets": tickets, "risk": risk, "keywords": text + " " + " ".join(str(t) for t in tickets)})
    return result


def choose(records: list[dict], required_session_ids: set[str], limit: int = 24) -> list[dict]:
    selected: list[dict] = []
    used: set[str] = set()
    def add(record: dict) -> None:
        if record["session_id"] not in used and len(selected) < limit:
            selected.append(record); used.add(record["session_id"])
    for session_id in required_session_ids:
        for record in records:
            if record["session_id"] == session_id:
                add(record); break
    # Force the four live scenarios by their business signals.
    signals = ("不良反应", "赠品", "承诺", "过敏", "投诉", "平台")
    for signal in signals:
        for record in records:
            if signal in record["keywords"]:
                add(record); break
    # Ensure each deterministic risk level has several reviewable examples.
    for level in ("critical", "high", "medium", "low"):
        for record in records:
            if record["risk"]["level"] == level:
                add(record)
                if sum(x["risk"]["level"] == level for x in selected) >= 4:
                    break
    # Add domain buckets not guaranteed by risk level.
    buckets = ("物流", "补发", "换货", "退款", "售后", "咨询")
    for bucket in buckets:
        for record in records:
            if bucket in record["keywords"] or bucket in record["major"] or bucket in record["minor"]:
                add(record); break
    for record in records:
        add(record)
        if len(selected) >= limit:
            break
    return selected


def to_csv_row(index: int, record: dict) -> dict[str, str]:
    # Keep source order and make each message auditable to a human reviewer.
    excerpt = "\n\n".join(f"[{m.get('sent_at') or 'time unavailable'}] {m.get('role') or m.get('sender') or 'unknown'}:\n{m.get('message_text') or m.get('chat_content') or ''}" for m in record["messages"])
    excerpt = excerpt[:2400]
    order_summary = " | ".join(f"{o.get('order_number','')} / {o.get('product_name','')} / {o.get('order_status','')} / gift={o.get('gift','')}" for o in record["orders"][:4])
    ticket_summary = " | ".join(f"{t.get('work_order_number','')} / {t.get('source_table','')} / {t.get('work_order_type', t.get('reaction_type', t.get('return_reason','')))} / {t.get('work_order_status', t.get('task_status',''))}" for t in record["tickets"][:6])
    reasons = " | ".join(f"{f['rule_id']}: {f['reason']}" for f in record["risk"]["findings"])
    return {"case_id": f"MG{index:03d}", "session_id": record["session_id"], "source_scene_major": record["major"], "source_scene_minor": record["minor"], "conversation_excerpt": excerpt, "relevant_order_summary": order_summary, "relevant_ticket_summary": ticket_summary, "rule_risk_level": record["risk"]["level"].upper(), "rule_risk_reasons": reasons, "human_intent_major": "", "human_intent_minor": "", "human_risk_level": "", "human_risk_reason": "", "human_required_tools": "", "human_review_notes": "", "human_review_status": ""}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite only after creating a backup; never use after human review starts")
    args = parser.parse_args()
    db = Path("data/beauty_cs_agent.sqlite3")
    output = Path("data/generated/evaluation/manual_gold_candidates.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        try:
            existing = []
            for encoding in ("utf-8-sig", "gb18030", "utf-16"):
                try:
                    with output.open(encoding=encoding, newline="") as handle:
                        existing = list(csv.DictReader(handle)); break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            human_fields = [f for f in FIELDS if f.startswith("human_")]
            if any((row.get(field) or "").strip() for row in existing for field in human_fields) and not args.force:
                print(json.dumps({"protected": True, "reason": "human annotations detected; refusing to overwrite CSV", "output": str(output)}, ensure_ascii=False))
                return
        except OSError as exc:
            print(json.dumps({"protected": True, "reason": f"unable to inspect existing CSV: {type(exc).__name__}", "output": str(output)}, ensure_ascii=False))
            return
    records = rows_from_db(db)
    with sqlite3.connect(db) as conn:
        required = set()
        for query in (
            "SELECT conversation_id FROM adverse_reaction_work_orders LIMIT 1",
            "SELECT conversation_id FROM replacement_work_orders LIMIT 1",
            "SELECT conversation_id FROM chat_messages GROUP BY conversation_id ORDER BY COUNT(*) DESC LIMIT 1",
            "SELECT conversation_id FROM chat_messages GROUP BY buyer_nickname, conversation_id HAVING COUNT(*) >= 6 ORDER BY COUNT(*) DESC LIMIT 1",
            "SELECT conversation_id FROM chat_messages WHERE message_text LIKE '%投诉%' OR message_text LIKE '%平台%' LIMIT 1",
        ):
            row = conn.execute(query).fetchone()
            if row and row[0]: required.add(str(row[0]))
    selected = choose(records, required, 24)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(to_csv_row(i, record) for i, record in enumerate(selected, 1))
    print(json.dumps({"output": str(output), "candidates": len(selected), "required_sessions": sorted(required), "risk_counts": {level: sum(r["risk"]["level"] == level for r in selected) for level in ("low", "medium", "high", "critical")}, "human_fields_blank": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
