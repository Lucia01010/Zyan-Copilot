"""Validate human annotations and export only DONE rows to Gold Set v1."""
from __future__ import annotations

import csv
import json
from pathlib import Path

RISK = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def read_rows(path: Path) -> tuple[list[dict[str, str]], str]:
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            with path.open(encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle)), encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError("unable to decode manual gold CSV")


def build(path: Path) -> tuple[list[dict[str, str]], dict[str, int], list[str]]:
    rows, _ = read_rows(path)
    counts = {"total_candidates": len(rows), "DONE": 0, "NEEDS_REVIEW": 0, "TODO": 0, "other_status": 0, "intent_eval_n": 0, "risk_eval_n": 0}
    errors: list[str] = []
    gold: list[dict[str, str]] = []
    for row in rows:
        status = (row.get("human_review_status") or "").strip().upper()
        if status in counts:
            counts[status] += 1
        elif status:
            counts["other_status"] += 1
        if status != "DONE":
            continue
        major = (row.get("human_intent_major") or "").strip()
        minor = (row.get("human_intent_minor") or "").strip()
        risk = (row.get("human_risk_level") or "").strip().upper()
        if not major or not minor:
            errors.append(f"{row.get('case_id')}: missing human intent")
            continue
        if risk not in RISK:
            errors.append(f"{row.get('case_id')}: invalid human risk {risk!r}")
            continue
        normalized = dict(row)
        normalized["human_risk_level"] = risk
        normalized["human_review_status"] = "DONE"
        # Required tools and notes intentionally remain exactly as supplied, including blank.
        gold.append(normalized)
        counts["intent_eval_n"] += 1
        counts["risk_eval_n"] += 1
    return gold, counts, errors


def main() -> None:
    source = Path("data/generated/evaluation/manual_gold_candidates.csv")
    output = Path("data/generated/evaluation/manual_gold_v1.jsonl")
    gold, counts, errors = build(source)
    if errors:
        print(json.dumps({"errors": errors, "counts": counts}, ensure_ascii=False, indent=2))
        raise SystemExit(2)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in gold:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "counts": counts, "errors": []}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
