"""Minimal interactive CSV reviewer; exports only explicitly completed rows to JSONL."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

RISK = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
TOOLS = {"order", "conversation_history", "adverse_reaction", "logistics", "replacement", "refund", "timeline"}


def review(input_path: Path, output_path: Path) -> None:
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for index, row in enumerate(rows, 1):
        print(f"\n[{index}/{len(rows)}] {row['case_id']} session={row['session_id']} source={row['source_scene_major']} / {row['source_scene_minor']}")
        print("证据摘要:", row["conversation_excerpt"])
        print("订单:", row["relevant_order_summary"] or "(无)")
        print("工单:", row["relevant_ticket_summary"] or "(无)")
        print("Rules:", row["rule_risk_level"], row["rule_risk_reasons"] or "(无)")
        row["human_intent_major"] = input("人工 intent major（可参考 source，必填，回车跳过）: ").strip()
        row["human_intent_minor"] = input("人工 intent minor（必填，回车跳过）: ").strip()
        row["human_risk_level"] = input("人工 risk LOW/MEDIUM/HIGH/CRITICAL（必填）: ").strip().upper()
        row["human_risk_reason"] = input("人工风险理由: ").strip()
        row["human_required_tools"] = input("required tools（逗号分隔）: ").strip()
        row["human_review_notes"] = input("复核备注: ").strip()
        if row["human_risk_level"] not in RISK or not row["human_intent_major"] or not row["human_intent_minor"]:
            row["human_review_status"] = "INCOMPLETE"
            print("未导出：intent/risk 未完成或 risk 值非法。")
            continue
        bad_tools = [x.strip() for x in row["human_required_tools"].split(",") if x.strip() and x.strip() not in TOOLS]
        if bad_tools:
            row["human_review_status"] = "INCOMPLETE"
            print("未导出：未知工具", bad_tools)
            continue
        row["human_review_status"] = "REVIEWED"
    completed = [row for row in rows if row["human_review_status"] == "REVIEWED"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in completed:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output_path), "reviewed": len(completed), "total": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/generated/evaluation/manual_gold_candidates.csv")
    parser.add_argument("--output", default="data/generated/evaluation/manual_gold.jsonl")
    args = parser.parse_args()
    review(Path(args.input), Path(args.output))
