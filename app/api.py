"""FastAPI application for the M3 service boundary."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from app.qwen_agent import BeautyAgent
from app.business_tools import BusinessTools
from app.action_registry import execute_action, format_action_result, recommend_actions
from app.config import load_env
from app.human_feedback import record_feedback
from app.risk_engine import assess_context
from app.task_state import get_task, list_tasks

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from pydantic import BaseModel
except ImportError:  # Optional local dependency; requirements.txt documents it.
    FastAPI = None


load_env()  # 配置外置化：读取任何配置前先加载仓库根目录 .env（已存在的真实环境变量优先）

DB_PATH = Path(os.getenv("BEAUTY_DB_PATH", "data/beauty_cs_agent.sqlite3"))
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


class SuggestRequest(BaseModel if FastAPI else object):
    conversation_id: str | None = None
    order_number: str | None = None
    buyer_nickname: str | None = None


class CopilotActionRequest(BaseModel if FastAPI else object):
    session_id: str


class CopilotChatRequest(BaseModel if FastAPI else object):
    session_id: str
    message: str


class CopilotFeedbackRequest(BaseModel if FastAPI else object):
    conversation_id: str
    original_reply: str
    edited_reply: str


def build_risk_detail(event: dict[str, Any], tools: BusinessTools) -> dict[str, Any]:
    """Expand a risk event with linked real customer/session evidence."""
    buyer = event.get("buyer_nickname")
    context = tools.get_customer_context(buyer) if buyer else {"orders": [], "work_orders": [], "messages": []}
    messages = sorted(context.get("messages", []), key=lambda item: (str(item.get("sent_at") or ""), str(item.get("message_sequence") or "")))
    session_ids = [str(item.get("conversation_id")) for item in messages if item.get("conversation_id")]
    detail = dict(event)
    detail.update({
        "customer": {"buyer_nickname": buyer},
        "session_id": session_ids[-1] if session_ids else None,
        "session": {"conversation_id": session_ids[-1] if session_ids else None, "buyer_nickname": buyer},
        "orders": context.get("orders", []),
        "work_orders": context.get("work_orders", []),
        "risk_reasons": [event.get("reason", "")],
        "service_timeline": messages[-8:],
        "current_status": event.get("status", "pending"),
    })
    return detail


def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed; run pip install -r requirements.txt")
    app = FastAPI(title="Beauty CS Agent API", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"], allow_methods=["*"], allow_headers=["*"])
    agent = BeautyAgent(DB_PATH)
    tools = BusinessTools(DB_PATH)

    def ensure_tracking_table() -> None:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS risk_tracking (risk_id TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            conn.commit()

    def risk_events() -> list[dict[str, Any]]:
        ensure_tracking_table()
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            buyers = [row[0] for row in conn.execute("SELECT DISTINCT buyer_nickname FROM chat_messages WHERE buyer_nickname IS NOT NULL")]
            statuses = {row[0]: dict(row) for row in conn.execute("SELECT risk_id, status, note, updated_at FROM risk_tracking")}
        events = []
        for buyer in buyers:
            context = tools.get_customer_context(buyer)
            result = assess_context(context)
            for finding in result["findings"]:
                risk_id = f"{buyer}:{finding['rule_id']}"
                events.append({"id": risk_id, "buyer_nickname": buyer, "status": statuses.get(risk_id, {}).get("status", "open"), "note": statuses.get(risk_id, {}).get("note", ""), **finding})
        return events

    @app.get("/health")
    def health() -> dict[str, Any]:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("SELECT 1")
            return {"status": "ok", "database": "ok", "provider": "mock" if agent.provider.mock else "qwen"}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc))

    @app.get("/api/agent/tasks")
    def agent_tasks(limit: int = 20) -> list[dict[str, Any]]:
        """原则 7：任务级全局状态观测列表（最新在前）。"""
        return list_tasks(DB_PATH, limit=limit)

    @app.get("/api/agent/tasks/{task_id}")
    def agent_task(task_id: str) -> dict[str, Any]:
        task = get_task(DB_PATH, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"unknown task: {task_id}")
        return task

    @app.post("/api/workbench/suggest")
    def suggest(request: SuggestRequest) -> dict[str, Any]:
        try:
            payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()
            result = agent.suggest(**payload)
            response = dict(result.__dict__)
            # Expose the linked risk event as navigation metadata only. The
            # Agent/Risk engine output itself remains unchanged.
            buyer = request.buyer_nickname
            if not buyer and request.conversation_id:
                messages = tools.get_conversation(request.conversation_id)
                buyer = messages[0].get("buyer_nickname") if messages else None
            linked = [event for event in risk_events() if buyer and event.get("buyer_nickname") == buyer]
            target_level = (result.hybrid_risk or {}).get("final_risk") or result.risk.get("level")
            rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            linked.sort(key=lambda event: (event.get("level") == target_level, rank.get(event.get("level"), 0)), reverse=True)
            response["risk_id"] = linked[0]["id"] if linked else None
            response["risk_ids"] = [event["id"] for event in linked]
            findings = []
            for finding in response.get("risk", {}).get("findings", []):
                item = dict(finding)
                item["risk_id"] = f"{buyer}:{item.get('rule_id')}" if buyer and item.get("rule_id") else None
                findings.append(item)
            response["risk"] = {**response.get("risk", {}), "findings": findings}
            if request.conversation_id:
                response["recommended_actions"] = recommend_actions(tools, request.conversation_id)
            return response
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/workbench/sessions")
    def sessions() -> dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT conversation_id, buyer_nickname, MAX(sent_at) AS last_message_at, COUNT(*) AS message_count, MAX(message_text) AS last_message FROM chat_messages WHERE conversation_id IS NOT NULL GROUP BY conversation_id, buyer_nickname ORDER BY last_message_at DESC LIMIT 100").fetchall()
        items = []
        for row in rows:
            item = dict(row)
            # Keep the list useful before analysis: derive a lightweight marker
            # from the same real customer context used by the risk engine.
            buyer_context = tools.get_customer_context(item.get("buyer_nickname"))
            risk = assess_context(buyer_context)
            item["risk_level"] = risk.get("level", "low")
            item["status"] = "待跟进" if risk.get("level") in {"high", "critical"} else "服务中"
            items.append(item)
        return {"items": items, "total": len(items)}

    @app.get("/api/workbench/sessions/{conversation_id}")
    def session_detail(conversation_id: str) -> dict[str, Any]:
        messages = tools.get_conversation(conversation_id)
        if not messages:
            raise HTTPException(status_code=404, detail="session not found")
        buyer = messages[0].get("buyer_nickname")
        context = tools.get_customer_context(buyer) if buyer else {"orders": [], "work_orders": [], "messages": messages}
        return {"conversation_id": conversation_id, "buyer_nickname": buyer, "messages": messages, "orders": context["orders"], "work_orders": context["work_orders"]}

    @app.get("/api/workbench/{session_id}/actions")
    def workbench_actions(session_id: str) -> dict[str, Any]:
        if not tools.get_conversation(session_id):
            raise HTTPException(status_code=404, detail="session not found")
        return {"session_id": session_id, "items": recommend_actions(tools, session_id)}

    @app.post("/api/copilot/actions/{action_id}")
    def copilot_action(action_id: str, request: CopilotActionRequest) -> dict[str, Any]:
        if not tools.get_conversation(request.session_id):
            raise HTTPException(status_code=404, detail="session not found")
        try:
            result = execute_action(tools, action_id, request.session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {**result, "message": format_action_result(result), "tools_used": [result.get("tool_name")]}

    @app.post("/api/copilot/chat")
    def copilot_chat(request: CopilotChatRequest) -> dict[str, Any]:
        if not tools.get_conversation(request.session_id):
            raise HTTPException(status_code=404, detail="session not found")
        text = request.message.strip()
        if not text:
            raise HTTPException(status_code=400, detail="message is required")
        actions = recommend_actions(tools, request.session_id)
        selected = next((item for item in actions if any(term in text for term in ("物流", "快递", "收到", "发货")) and item["action_id"] == "check_logistics"), None)
        selected = selected or next((item for item in actions if any(term in text for term in ("退款", "到账", "打款")) and item["action_id"] in {"check_refund", "check_payment"}), None)
        selected = selected or (actions[0] if actions else None)
        if not selected:
            return {"session_id": request.session_id, "message": "当前没有可执行的业务查询，请提供更具体的问题。", "tools_used": [], "evidence": []}
        result = execute_action(tools, selected["action_id"], request.session_id)
        return {"session_id": request.session_id, "message": format_action_result(result), "tools_used": [result.get("tool_name")], "evidence": [{"source": result.get("source"), "status": result.get("status"), "action_id": result.get("action_id")}]}

    @app.post("/api/copilot/feedback")
    def copilot_feedback(request: CopilotFeedbackRequest) -> dict[str, Any]:
        """原则 3 人机协同工具化：人工修改建议回复落库为结构化事件，补全审计链。"""
        if not tools.get_conversation(request.conversation_id):
            raise HTTPException(status_code=404, detail="session not found")
        try:
            feedback_id = record_feedback(DB_PATH, request.conversation_id, request.original_reply, request.edited_reply)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"feedback_id": feedback_id, "conversation_id": request.conversation_id, "recorded": True}

    @app.get("/api/risks")
    def risks(level: str | None = None, status: str | None = None) -> dict[str, Any]:
        events = risk_events()
        if level:
            events = [event for event in events if event["level"] == level]
        if status:
            events = [event for event in events if event["status"] == status]
        return {"items": events, "total": len(events)}

    @app.get("/api/risks/{risk_id}")
    def risk_detail(risk_id: str) -> dict[str, Any]:
        event = next((event for event in risk_events() if event["id"] == risk_id), None)
        if event is None:
            raise HTTPException(status_code=404, detail="risk event not found")
        return build_risk_detail(event, tools)

    @app.patch("/api/risks/{risk_id}")
    def update_risk(risk_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = {"pending", "open", "processing", "resolved", "ignored"}
        status = payload.get("status")
        if status not in allowed:
            raise HTTPException(status_code=400, detail="status must be open, processing, resolved or ignored")
        event = next((event for event in risk_events() if event["id"] == risk_id), None)
        if event is None:
            raise HTTPException(status_code=404, detail="risk event not found")
        ensure_tracking_table()
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO risk_tracking(risk_id, status, note) VALUES (?, ?, ?) ON CONFLICT(risk_id) DO UPDATE SET status=excluded.status, note=excluded.note, updated_at=CURRENT_TIMESTAMP", (risk_id, status, payload.get("note", "")))
            conn.commit()
        event["status"] = status
        event["note"] = payload.get("note", "")
        return build_risk_detail(event, tools)

    @app.get("/api/customers/{buyer_nickname}/summary")
    def customer_summary(buyer_nickname: str) -> dict[str, Any]:
        return tools.get_customer_context(buyer_nickname)

    @app.get("/api/orders/{order_number}")
    def order_detail(order_number: str) -> dict[str, Any]:
        order = tools.get_order(order_number)
        if order is None:
            raise HTTPException(status_code=404, detail="order not found")
        return order

    @app.get("/api/evaluation/costs")
    def costs() -> dict[str, Any]:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), COALESCE(AVG(latency_ms),0) FROM agent_runs").fetchone()
        return {"runs": row[0], "input_tokens": row[1], "output_tokens": row[2], "avg_latency_ms": row[3]}

    # 生产/演示形态：后端直接托管已构建的前端（frontend/dist），单进程即可访问 /workbench。
    # 必须在所有 API 路由之后注册；dist 不存在时（如纯后端测试）自动跳过。
    if FRONTEND_DIST.is_dir():
        dist_root = FRONTEND_DIST.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_entry(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="not found")
            candidate = (dist_root / full_path).resolve()
            if full_path and candidate.is_relative_to(dist_root) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist_root / "index.html")

    return app


app = create_app() if FastAPI is not None else None
