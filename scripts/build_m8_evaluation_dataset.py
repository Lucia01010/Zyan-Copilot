"""Build a provenance-preserving M8 evaluation dataset from imported business data."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def build(db: Path) -> dict:
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        conversations = conn.execute("SELECT conversation_id, buyer_nickname, COUNT(*) AS message_count, GROUP_CONCAT(DISTINCT scene_major) AS scene_major_values, GROUP_CONCAT(DISTINCT scene_minor) AS scene_minor_values FROM chat_messages WHERE conversation_id IS NOT NULL GROUP BY conversation_id, buyer_nickname ORDER BY conversation_id").fetchall()
        rows = []
        for item in conversations:
            cid = item["conversation_id"]
            buyer = item["buyer_nickname"]
            work = conn.execute("SELECT work_order_number, work_order_type, after_sales_reason FROM replacement_work_orders WHERE conversation_id = ? UNION ALL SELECT work_order_number, 'adverse_reaction', reaction_type FROM adverse_reaction_work_orders WHERE conversation_id = ? UNION ALL SELECT work_order_number, 'after_sales_return', return_reason FROM after_sales_return_work_orders WHERE conversation_id = ?", (cid, cid, cid)).fetchall()
            rows.append({
                "conversation_id": str(cid),
                "buyer_nickname": str(buyer) if buyer is not None else None,
                "message_count": int(item["message_count"]),
                "source_labels": {
                    "scene_major": [x for x in (item["scene_major_values"] or "").split(",") if x],
                    "scene_minor": [x for x in (item["scene_minor_values"] or "").split(",") if x],
                    "work_order_types": [dict(x)["work_order_type"] for x in work if dict(x)["work_order_type"]],
                    "after_sales_reasons": [dict(x)["after_sales_reason"] for x in work if dict(x)["after_sales_reason"]],
                },
                "label_provenance": {
                    "source_derived": ["chat_messages.scene_major", "chat_messages.scene_minor", "work_order_type", "after_sales_reason"],
                    "rule_derived": ["risk_engine.assess_context"],
                    "manually_reviewed": "unavailable",
                    "model_generated": "not_ground_truth",
                },
            })
    return {"dataset_version": "m8.0", "source_db": str(db), "records": rows}


def main() -> None:
    db = Path("data/beauty_cs_agent.sqlite3")
    output = Path("data/generated/evaluation/m8_dataset.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build(db)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "records": len(payload["records"]), "source_label_records": sum(bool(r["source_labels"]["scene_major"] or r["source_labels"]["scene_minor"]) for r in payload["records"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
