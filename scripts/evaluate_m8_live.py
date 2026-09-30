"""Small, budget-guarded M8 live comparison: LLM-only vs proposed Agent."""
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
from app.qwen_agent import AgentOutput, BeautyAgent, QwenProvider, QuotaExhaustedError


def load_gold(db_path: Path) -> list[dict]:
    path = Path("data/generated/evaluation/manual_gold_v1.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    with sqlite3.connect(db_path) as conn:
        buyers = {str(cid): buyer for cid, buyer in conn.execute("SELECT conversation_id, buyer_nickname FROM chat_messages WHERE conversation_id IS NOT NULL GROUP BY conversation_id, buyer_nickname")}
    for row in rows:
        row["buyer_nickname"] = buyers.get(str(row["session_id"]))
    return rows


def choose_sample(rows: list[dict], max_n: int) -> list[dict]:
    chosen: list[dict] = []
    used: set[str] = set()
    # Case C is mandatory; add one low and one high/critical for a minimal risk spread.
    for predicate in (
        lambda r: r["session_id"] == "S00075",
        lambda r: r["human_risk_level"] == "LOW",
        lambda r: r["human_risk_level"] in {"HIGH", "CRITICAL"},
    ):
        row = next((r for r in rows if predicate(r) and r["session_id"] not in used), None)
        if row:
            chosen.append(row); used.add(row["session_id"])
    for row in rows:
        if len(chosen) >= max_n: break
        if row["session_id"] not in used:
            chosen.append(row); used.add(row["session_id"])
    return chosen[:max_n]


def parse_model_output(content: str) -> tuple[dict, bool]:
    parsed = QwenProvider._parse_json(content)
    try:
        AgentOutput.model_validate(parsed)
        return parsed, True
    except Exception:
        return parsed, False


def run_llm_only(provider: QwenProvider, tools: BusinessTools, row: dict) -> dict:
    started = time.perf_counter()
    messages = tools.get_conversation(row["session_id"], limit=8)
    # Deliberately no orders, work orders, customer context, or business tools.
    context = [{"sent_at": m.get("sent_at"), "role": m.get("role"), "message_text": m.get("message_text") or m.get("chat_content")} for m in messages]
    schema = provider._api_schema()
    system = f"你是只读聊天分类基线。只能根据提供的聊天消息回答，不得调用工具、猜测订单/工单事实。只输出严格 JSON，符合 schema：{json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}。未知业务事实写入 missing_information。"
    body = provider._request([{"role": "system", "content": system}, {"role": "user", "content": json.dumps({"messages": context}, ensure_ascii=False)}], [], response_format={"type": "json_schema", "json_schema": {"name": "agent_output", "schema": schema, "strict": True}}, stage="m8_llm_only")
    usage = body.get("usage", {})
    choice = body.get("choices", [{}])[0]
    content = str(choice.get("message", {}).get("content", ""))
    output, valid = parse_model_output(content)
    return {"mode": "llm_only", "provider": provider.provider, "model": provider.model, "tools_called": [], "tool_call_sequence": [], "finish_reason": choice.get("finish_reason"), "model_output": output, "structured_output_valid": valid, "repair_used": False, "errors": [] if valid else ["structured_output_invalid"], "input_tokens": usage.get("prompt_tokens", 0) or 0, "output_tokens": usage.get("completion_tokens", 0) or 0, "total_tokens": usage.get("total_tokens", (usage.get("prompt_tokens", 0) or 0) + (usage.get("completion_tokens", 0) or 0)) or 0, "latency_ms": int((time.perf_counter() - started) * 1000), "context_only": True}


def grounded(output: dict, context: dict) -> tuple[bool, list[str]]:
    corpus = json.dumps(context, ensure_ascii=False)
    claims = re.findall(r"\b\d{8,}\b|\b[A-Z]{1,5}\d{6,}\b", json.dumps(output, ensure_ascii=False))
    unknown = [claim for claim in claims if claim not in corpus]
    return not unknown, unknown


def main() -> int:
    if os.getenv("AGENT_PROVIDER") != "qwen" or not os.getenv("QWEN_API_KEY"):
        print(json.dumps({"blocked": "AGENT_PROVIDER=qwen and QWEN_API_KEY are required", "pass": False}, ensure_ascii=False)); return 2
    budget = int(os.getenv("QWEN_EVAL_TOKEN_BUDGET", "60000"))
    estimate = int(os.getenv("QWEN_EVAL_ESTIMATED_PAIR_TOKENS", "20000"))
    guard = TokenBudgetGuard(budget, estimate_per_case=estimate)
    db_path = Path(os.getenv("BEAUTY_DB_PATH", "data/beauty_cs_agent.sqlite3"))
    gold = load_gold(db_path)
    max_n = min(12, budget // estimate)
    sample = choose_sample(gold, max_n)
    provider = QwenProvider()
    tools = BusinessTools(db_path)
    agent = BeautyAgent(tools.db_path, provider)
    output_path = Path("data/generated/evaluation/live_results.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    # Append this evaluation run; prior live evidence must remain immutable.
    with output_path.open("a", encoding="utf-8") as handle:
        for row in sample:
            if not guard.can_start():
                break
            try:
                llm = run_llm_only(provider, tools, row)
                agent_started = time.perf_counter()
                agent_result = agent.suggest(buyer_nickname=row["buyer_nickname"])
                context = tools.get_customer_context(row["buyer_nickname"])
                agent_record = {"mode": "agent", "provider": agent_result.provider, "model": agent_result.model, "tools_called": agent_result.tool_calls, "tool_call_sequence": agent_result.tool_calls, "finish_reason": agent_result.finish_reason, "model_output": agent_result.model_output or {}, "structured_output_valid": agent_result.structured_output_valid, "repair_used": agent_result.repair_used, "errors": agent_result.errors or [], "input_tokens": agent_result.input_tokens or 0, "output_tokens": agent_result.output_tokens or 0, "total_tokens": (agent_result.input_tokens or 0) + (agent_result.output_tokens or 0), "latency_ms": agent_result.latency_ms, "rule_risk": agent_result.risk, "hybrid_risk": agent_result.hybrid_risk, "context_only": False}
                llm["grounding_pass"], llm["unsupported_claims"] = grounded(llm["model_output"], {"messages": tools.get_conversation(row["session_id"], 8)})
                agent_record["grounding_pass"], agent_record["unsupported_claims"] = grounded(agent_record["model_output"], context)
                record = {"case_id": row["case_id"], "session_id": row["session_id"], "human_intent_major": row["human_intent_major"], "human_intent_minor": row["human_intent_minor"], "human_risk_level": row["human_risk_level"], "llm_only": llm, "agent": agent_record, "model_risk": agent_record["model_output"].get("risk_level"), "rule_risk": agent_record["rule_risk"].get("level"), "final_hybrid_risk": (agent_record["hybrid_risk"] or {}).get("final_risk"), "hybrid_status": "implemented"}
                handle.write(json.dumps(record, ensure_ascii=False) + "\n"); handle.flush(); results.append(record)
                guard.record(llm["total_tokens"] + agent_record["total_tokens"])
            except QuotaExhaustedError as exc:
                print(json.dumps({"blocked": str(exc), "cases_completed": len(results), "tokens_used": guard.used, "pass": False}, ensure_ascii=False)); return 3
            except Exception as exc:
                print(json.dumps({"blocked": "case failed", "error_type": type(exc).__name__, "cases_completed": len(results), "tokens_used": guard.used, "pass": False}, ensure_ascii=False)); return 5
    print(json.dumps({"sample_size": len(results), "selected_case_ids": [r["case_id"] for r in results], "tokens_used": guard.used, "token_budget": budget, "output": str(output_path), "pass": bool(results)}, ensure_ascii=False, indent=2))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
