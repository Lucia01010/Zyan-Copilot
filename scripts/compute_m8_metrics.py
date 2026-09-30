"""Compute honest M8 metrics from Gold v1 and small live results."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.intent_taxonomy import IntentTaxonomy

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def confusion(rows: list[tuple[str, str]]) -> dict:
    return {actual: {pred: sum(a == actual and p == pred for a, p in rows) for pred in LEVELS} for actual in LEVELS}


def accuracy(rows: list[tuple[str, str]]) -> float | None:
    return round(sum(a == p for a, p in rows) / len(rows), 4) if rows else None


def risk_metrics(results: list[dict], getter) -> dict:
    pairs = [(r["human_risk_level"], (getter(r) or "").upper()) for r in results if getter(r)]
    high_actual = [p for p in pairs if p[0] in {"HIGH", "CRITICAL"}]
    high_recall = (sum(p[1] in {"HIGH", "CRITICAL"} for p in high_actual) / len(high_actual)) if high_actual else None
    low_actual = [p for p in pairs if p[0] == "LOW"]
    false_escalation = (sum(p[1] in {"HIGH", "CRITICAL"} for p in low_actual) / len(low_actual)) if low_actual else None
    return {"N": len(pairs), "accuracy": accuracy(pairs), "high_risk_recall": None if high_recall is None else round(high_recall, 4), "false_escalation_rate": None if false_escalation is None else round(false_escalation, 4), "confusion_matrix": confusion(pairs)}


def intent_metrics(results: list[dict], mode: str, taxonomy: IntentTaxonomy) -> dict:
    major = []
    minor = []
    combined = []
    for r in results:
        output = r[mode].get("model_output", {})
        mapped = taxonomy.normalize(str(output.get("intent_major", "")), str(output.get("intent_minor", ""))) or taxonomy.map_text(str(output.get("intent", "")))
        if r["human_intent_major"]:
            gold = (r["human_intent_major"], r["human_intent_minor"])
            predicted = mapped or ("__UNMAPPED__", "__UNMAPPED__")
            major.append((gold[0], predicted[0])); minor.append((gold[1], predicted[1])); combined.append((gold, predicted))
    return {"N": len(combined), "major_accuracy": accuracy(major), "minor_accuracy": accuracy(minor), "combined_accuracy": accuracy(combined), "taxonomy": "Gold v1-derived IntentTaxonomy"}


def main() -> None:
    path = Path("data/generated/evaluation/live_results.jsonl")
    results = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    gold_rows = [{"human_intent_major": r["human_intent_major"], "human_intent_minor": r["human_intent_minor"]} for r in results]
    taxonomy_path = Path("data/generated/evaluation/intent_taxonomy.json")
    if taxonomy_path.exists():
        taxonomy_data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        taxonomy = IntentTaxonomy({key: tuple(value) for key, value in taxonomy_data["major_to_minors"].items()})
    else:
        taxonomy = IntentTaxonomy.from_rows(gold_rows)
    hybrid_rows = [r for r in results if r.get("final_hybrid_risk")]
    latest_batch = results[-3:] if len(results) >= 3 else results
    report = {
        "status": "MEASURED_WITH_LIMITATIONS",
        "sample_N": len(results),
        "intent": {"llm_only": intent_metrics(results, "llm_only", taxonomy), "agent": intent_metrics(results, "agent", taxonomy)},
        "risk": {"rules_vs_human": risk_metrics(results, lambda r: r.get("rule_risk")), "llm_only_vs_human": risk_metrics(results, lambda r: r["llm_only"]["model_output"].get("risk_level")), "agent_model_risk_vs_human": risk_metrics(results, lambda r: r.get("model_risk")), "final_hybrid_risk_vs_human": risk_metrics(hybrid_rows, lambda r: r.get("final_hybrid_risk")) if hybrid_rows else "NOT MEASURED"},
        "agent_quality": {
            "structured_output_valid_rate": round(sum(r["agent"]["structured_output_valid"] for r in results) / len(results), 4) if results else None,
            "grounding_pass_rate": round(sum(r["agent"].get("grounding_pass", False) for r in results) / len(results), 4) if results else None,
            "unsupported_fact_rate": round(sum(bool(r["agent"].get("unsupported_claims")) for r in results) / len(results), 4) if results else None,
            "tool_call_success_rate": round(sum(bool(r["agent"].get("tools_called")) for r in results) / len(results), 4) if results else None,
            "repair_rate": round(sum(r["agent"].get("repair_used", False) for r in results) / len(results), 4) if results else None,
            "tool_selection_accuracy": "NOT YET MEASURABLE — awaiting second-round tool gold annotation",
            "required_tool_recall": "NOT YET MEASURABLE — awaiting second-round tool gold annotation",
        },
        "efficiency": {mode: {"N": len(results), "avg_latency_ms": round(sum(r[mode]["latency_ms"] for r in results) / len(results), 2) if results else None, "avg_input_tokens": round(sum(r[mode]["input_tokens"] for r in results) / len(results), 2) if results else None, "avg_output_tokens": round(sum(r[mode]["output_tokens"] for r in results) / len(results), 2) if results else None, "avg_total_tokens": round(sum(r[mode]["total_tokens"] for r in results) / len(results), 2) if results else None} for mode in ("llm_only", "agent")},
        "case_c": next(({"human": r["human_risk_level"], "rules": r.get("rule_risk"), "llm_only": r["llm_only"]["model_output"].get("risk_level"), "agent_model_risk": r.get("model_risk"), "rule_floor": (r.get("agent", {}).get("hybrid_risk") or {}).get("rule_floor"), "final_hybrid_risk": r.get("final_hybrid_risk"), "applied_rules": (r.get("agent", {}).get("hybrid_risk") or {}).get("applied_rules", []), "risk_reasons": (r.get("agent", {}).get("hybrid_risk") or {}).get("reasons", []), "status": "GOLD_V1_DISAGREEMENT" if r.get("final_hybrid_risk") is None else "MEASURED"} for r in reversed(results) if r["session_id"] == "S00075"), {"status": "NOT_IN_SAMPLE"}),
        "latest_batch": {"N": len(latest_batch), "agent_avg_total_tokens": round(sum(r["agent"]["total_tokens"] for r in latest_batch) / len(latest_batch), 2) if latest_batch else None, "llm_only_avg_total_tokens": round(sum(r["llm_only"]["total_tokens"] for r in latest_batch) / len(latest_batch), 2) if latest_batch else None, "agent_avg_latency_ms": round(sum(r["agent"]["latency_ms"] for r in latest_batch) / len(latest_batch), 2) if latest_batch else None, "llm_only_avg_latency_ms": round(sum(r["llm_only"]["latency_ms"] for r in latest_batch) / len(latest_batch), 2) if latest_batch else None},
    }
    output = Path("data/generated/evaluation/metrics.json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
