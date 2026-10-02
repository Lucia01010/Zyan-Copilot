"""FastAPI application for the M3 service boundary."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from app.qwen_agent import BeautyAgent
from app.business_tools import BusinessTools
from app.risk_engine import assess_context

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:  # Optional local dependency; requirements.txt documents it.
    FastAPI = None


DB_PATH = Path(os.getenv("BEAUTY_DB_PATH", "data/beauty_cs_agent.sqlite3"))


class SuggestRequest(BaseModel if FastAPI else object):
    conversation_id: str | None = None
    order_number: str | None = None
    buyer_nickname: str | None = None


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

    @app.post("/api/workbench/suggest")
    def suggest(request: SuggestRequest) -> dict[str, Any]:
        try:
            payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()
            result = agent.suggest(**payload)
            return result.__dict__
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

    return app


app = create_app() if FastAPI is not None else None
