"""Run a repeatable offline evaluation of Tools, rules and mock Agent."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.business_tools import BusinessTools
from app.qwen_agent import BeautyAgent, QwenProvider


def main() -> None:
    db = Path("data/beauty_cs_agent.sqlite3")
    with sqlite3.connect(db) as conn:
        buyers = [row[0] for row in conn.execute("SELECT DISTINCT buyer_nickname FROM chat_messages WHERE buyer_nickname IS NOT NULL")]
    tools = BusinessTools(db)
    agent = BeautyAgent(db, QwenProvider(mock=True))
    runs = []
    for buyer in buyers:
        context = tools.get_customer_context(buyer)
        result = agent.suggest(buyer_nickname=buyer)
        runs.append({"buyer": buyer, "orders": len(context["orders"]), "messages": len(context["messages"]), "work_orders": len(context["work_orders"]), "risk_level": result.risk["level"], "finding_count": len(result.risk["findings"]), "provider": result.provider, "input_tokens": result.input_tokens or 0, "output_tokens": result.output_tokens or 0, "latency_ms": result.latency_ms, "tool_calls": result.tool_calls})
    report = {"provider": "mock", "customers_evaluated": len(runs), "risk_counts": {level: sum(run["risk_level"] == level for run in runs) for level in ("low", "medium", "high", "critical")}, "total_findings": sum(run["finding_count"] for run in runs), "input_tokens": sum(run["input_tokens"] for run in runs), "output_tokens": sum(run["output_tokens"] for run in runs), "avg_latency_ms": round(sum(run["latency_ms"] for run in runs) / len(runs), 2) if runs else 0, "tool_call_success_rate": 1.0 if all(run["tool_calls"] for run in runs) else 0.0, "sample": runs[:3]}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
