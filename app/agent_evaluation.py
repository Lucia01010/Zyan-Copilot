"""M21 Agent Evaluation System：四指标离线评估基线。

指标：
1. Tool Accuracy——是否调用正确工具（expected 全命中 且 forbidden 零命中）
2. Retrieval Accuracy——检索首位切片是否命中期望文档/小节
3. Hallucination Rate——grounding 判定无依据的回复占比（必须为 0）
4. Memory Accuracy——多轮场景中 memory/状态机制是否生效（plan 去重、指代消解）

运行：`python -m app.agent_evaluation`（打印 JSON 报告）；测试层断言指标阈值。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agent_brain import SessionMemory, process_message
from app.business_tools import BusinessTools
from app.context_engine import ContextEngine
from app.conversation_state import ConversationStateMachine
from app.knowledge_base import KnowledgeStore

GOLD_PATH = Path(__file__).resolve().parents[1] / "tests" / "gold" / "agent_eval_cases.json"

# 指标阈值：低于阈值视为回归
THRESHOLDS = {"tool_accuracy": 0.8, "retrieval_accuracy": 0.8, "hallucination_rate": 0.0, "memory_accuracy": 1.0}


def load_gold_cases(path: Path | None = None) -> dict[str, Any]:
    with open(path or GOLD_PATH, encoding="utf-8") as fp:
        return json.load(fp)


def evaluate_agent(db_path: str | Path, knowledge_dir: str | Path, gold_path: Path | None = None) -> dict[str, Any]:
    tools = BusinessTools(db_path)
    engine = ContextEngine(db_path)
    store = KnowledgeStore(db_path, knowledge_dir)
    store.ensure_index()
    state_machine = ConversationStateMachine(str(db_path))
    memory = SessionMemory()  # 评估用独立记忆，不污染服务进程
    cases = load_gold_cases(gold_path)

    tool_details: list[dict[str, Any]] = []
    ungrounded = 0
    for case in cases.get("tool_cases", []):
        result = process_message(tools, case["session_id"], case["message"], knowledge_store=store, context_engine=engine, memory=memory, state_machine=state_machine)
        used = result.get("tools_used", [])
        expected_hit = all(tool in used for tool in case.get("expected_tools", []))
        forbidden_hit = any(tool in used for tool in case.get("forbidden_tools", []))
        grounded = result.get("grounding", {}).get("grounded", True)
        if not grounded:
            ungrounded += 1
        tool_details.append({"id": case["id"], "passed": expected_hit and not forbidden_hit, "tools_used": used, "grounded": grounded})

    retrieval_details: list[dict[str, Any]] = []
    for case in cases.get("retrieval_cases", []):
        chunks = store.search(case["query"], top_k=1)
        hit = bool(chunks) and chunks[0].doc_title == case["expected_doc"] and case["expected_section_contains"] in chunks[0].section
        retrieval_details.append({"id": case["id"], "passed": hit, "top": (chunks[0].doc_title + "·" + chunks[0].section) if chunks else None})

    memory_details: list[dict[str, Any]] = []
    for case in cases.get("memory_cases", []):
        case_memory = SessionMemory()
        results = [process_message(tools, case["session_id"], turn, knowledge_store=store, context_engine=engine, memory=case_memory, state_machine=state_machine) for turn in case["turns"]]
        passed = False
        if case.get("assertion") == "second_turn_plan_dedup" and len(results) == 2:
            passed = [step["action"] for step in results[1].get("plan", [])] == ["assess_customer_risk"]
        memory_details.append({"id": case["id"], "passed": passed, "second_plan": [step["action"] for step in results[-1].get("plan", [])] if results else []})

    total_tool = max(1, len(tool_details))
    total_rag = max(1, len(retrieval_details))
    total_mem = max(1, len(memory_details))
    metrics = {
        "tool_accuracy": round(sum(1 for item in tool_details if item["passed"]) / total_tool, 4),
        "retrieval_accuracy": round(sum(1 for item in retrieval_details if item["passed"]) / total_rag, 4),
        "hallucination_rate": round(ungrounded / total_tool, 4),
        "memory_accuracy": round(sum(1 for item in memory_details if item["passed"]) / total_mem, 4),
    }
    thresholds_met = {
        "tool_accuracy": metrics["tool_accuracy"] >= THRESHOLDS["tool_accuracy"],
        "retrieval_accuracy": metrics["retrieval_accuracy"] >= THRESHOLDS["retrieval_accuracy"],
        "hallucination_rate": metrics["hallucination_rate"] <= THRESHOLDS["hallucination_rate"],
        "memory_accuracy": metrics["memory_accuracy"] >= THRESHOLDS["memory_accuracy"],
    }
    return {"metrics": metrics, "thresholds": THRESHOLDS, "thresholds_met": thresholds_met, "all_passed": all(thresholds_met.values()), "details": {"tool_cases": tool_details, "retrieval_cases": retrieval_details, "memory_cases": memory_details}}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = evaluate_agent(root / "data/beauty_cs_agent.sqlite3", root / "knowledge")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
