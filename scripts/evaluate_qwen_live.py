"""Run four real Qwen regression cases with bounded tool-calling evidence.

Requires AGENT_PROVIDER=qwen and QWEN_API_KEY. It exits with code 2 when the
credential is absent so mock output cannot be mistaken for live verification.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.business_tools import BusinessTools
from app.evaluation import TokenBudgetGuard
from app.qwen_agent import BeautyAgent, QwenProvider, QuotaExhaustedError


def pick_cases(db: Path) -> dict[str, dict[str, str]]:
    with sqlite3.connect(db) as conn:
        adverse = conn.execute("SELECT buyer_nickname, conversation_id FROM adverse_reaction_work_orders LIMIT 1").fetchone()
        replacement = conn.execute("SELECT buyer_nickname, conversation_id FROM replacement_work_orders LIMIT 1").fetchone()
        promise = conn.execute("SELECT buyer_nickname, conversation_id FROM chat_messages GROUP BY buyer_nickname, conversation_id HAVING COUNT(*) >= 6 ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
        escalation = conn.execute("SELECT buyer_nickname, conversation_id FROM chat_messages WHERE message_text LIKE '%投诉%' OR message_text LIKE '%平台%' LIMIT 1").fetchone()
    rows = {"A_allergy_batch": adverse, "B_gift_missing": replacement, "C_promise_conflict": promise, "D_emotion_escalation": escalation}
    return {name: {"buyer_nickname": row[0], "conversation_id": row[1]} for name, row in rows.items() if row}


def evidence_claims_are_grounded(output: dict, context: dict) -> tuple[bool, list[str]]:
    corpus = json.dumps(context, ensure_ascii=False)
    claims = re.findall(r"\b\d{8,}\b|\b[A-Z]{1,5}\d{6,}\b", json.dumps(output, ensure_ascii=False))
    unknown = [claim for claim in claims if claim not in corpus]
    return not unknown, unknown


def main() -> int:
    if os.getenv("AGENT_PROVIDER") != "qwen" or not os.getenv("QWEN_API_KEY"):
        print(json.dumps({"blocked": "Set AGENT_PROVIDER=qwen and QWEN_API_KEY to run real Qwen verification.", "mock_is_not_live": True}, ensure_ascii=False))
        return 2
    db = Path(os.getenv("BEAUTY_DB_PATH", "data/beauty_cs_agent.sqlite3"))
    provider = QwenProvider()
    budget = int(os.getenv("QWEN_EVAL_TOKEN_BUDGET", "50000"))
    estimate = int(os.getenv("QWEN_EVAL_ESTIMATED_CASE_TOKENS", "15000"))
    guard = TokenBudgetGuard(budget=budget, estimate_per_case=estimate)
    selected_case = os.getenv("QWEN_LIVE_CASE")
    selected_cases = [item.strip() for item in os.getenv("QWEN_LIVE_CASES", "").split(",") if item.strip()]
    cases = pick_cases(db)
    all_names = ("A_allergy_batch", "B_gift_missing", "C_promise_conflict", "D_emotion_escalation")
    case_names = [name for name in all_names if name in cases and (not selected_case or name == selected_case) and (not selected_cases or name in selected_cases)]
    if provider.free_only:
        case_names = case_names[:4]
    agent = BeautyAgent(db, provider)
    tools = BusinessTools(db)
    results = []
    used_tokens = 0
    for case in case_names:
        if not guard.can_start():
            print(json.dumps({"provider": provider.provider, "model": provider.model, "blocked": "QWEN_EVAL_TOKEN_BUDGET insufficient for conservative next-case estimate", "token_budget": budget, "estimated_case_tokens": estimate, "tokens_used": used_tokens, "remaining_tokens": guard.remaining, "cases": results, "pass": False}, ensure_ascii=False, indent=2))
            return 4
        identifiers = cases[case]
        started = time.perf_counter()
        try:
            result = agent.suggest(**identifiers)
        except QuotaExhaustedError as exc:
            print(json.dumps({"provider": provider.provider, "blocked": str(exc), "token_budget": budget, "tokens_used": used_tokens, "cases_completed": len(results), "pass": False}, ensure_ascii=False, indent=2))
            return 3
        except Exception as exc:
            print(json.dumps({"provider": provider.provider, "model": provider.model, "blocked": "live case failed", "error_type": type(exc).__name__, "token_budget": budget, "tokens_used": used_tokens, "cases_completed": len(results), "pass": False}, ensure_ascii=False, indent=2))
            return 5
        context = tools.get_customer_context(identifiers["buyer_nickname"])
        used_tokens += (result.input_tokens or 0) + (result.output_tokens or 0)
        guard.record((result.input_tokens or 0) + (result.output_tokens or 0))
        grounded, unknown = evidence_claims_are_grounded(result.model_output or {}, context)
        results.append({"case": case, "user_session": identifiers, "tools_called": result.tool_calls, "tool_call_sequence": result.tool_calls, "model_output": result.model_output, "structured_output_valid": result.structured_output_valid, "response_format_mode": result.response_format_mode, "finish_reason": result.finish_reason, "raw_final_content": result.raw_final_content, "repair_used": result.repair_used, "risk": result.risk, "latency_ms": int((time.perf_counter() - started) * 1000), "input_tokens": result.input_tokens, "output_tokens": result.output_tokens, "total_tokens": (result.input_tokens or 0) + (result.output_tokens or 0), "usage_records": result.usage_records or [], "errors": result.errors or [], "evidence_grounded": grounded, "unknown_claims": unknown})
        if used_tokens > budget:
            print(json.dumps({"provider": provider.provider, "model": provider.model, "blocked": "QWEN_EVAL_TOKEN_BUDGET exceeded by an already-started request; no further case will start", "token_budget": budget, "tokens_used": used_tokens, "cases": results, "pass": False}, ensure_ascii=False, indent=2))
            return 4
    print(json.dumps({"provider": provider.provider, "model": provider.model, "free_only": provider.free_only, "token_budget": budget, "tokens_used": used_tokens, "cases": results}, ensure_ascii=False, indent=2))
    expected = len(case_names)
    return 0 if len(results) == expected and all(item["structured_output_valid"] and item["evidence_grounded"] and item["tools_called"] and not item["repair_used"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
