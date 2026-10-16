"""Qwen-compatible agent with bounded tool calling and an offline mock provider."""
from __future__ import annotations

import json
import os
import time
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.business_tools import BusinessTools
from app.config import load_env
from app.context_arbiter import arbitrate_messages, arbitrate_orders
from app.context_engine import ContextEngine
from app.error_compactor import compact_tool_error
from app.hybrid_risk import hybrid_risk
from app.intent_taxonomy import IntentTaxonomy
from app.risk_engine import assess_context
from app.task_state import record_task, update_task

load_env()  # 配置外置化：导入即加载仓库根目录 .env（已存在的真实环境变量优先，不被覆盖）

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_PROMPT_CACHE: dict[str, str] = {}


def load_prompt(name: str, **values: str) -> str:
    """读取 app/prompts/<name>.txt 提示词模板并替换 {placeholder}；首次读取后缓存。

    提示词外置化（12-Factor 原则 4）：模板独立于代码版本管理与回滚，修改提示词无需改代码。
    """
    template = _PROMPT_CACHE.get(name)
    if template is None:
        template = (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
        _PROMPT_CACHE[name] = template
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "get_conversation", "description": "查询指定会话的有限条消息。只能用于已有 conversation_id。", "parameters": {"type": "object", "properties": {"conversation_id": {"type": "string"}, "limit": {"type": "integer", "maximum": 50}}, "required": ["conversation_id"]}}},
    {"type": "function", "function": {"name": "get_order", "description": "按精确字符串订单号查询订单。找不到时返回 null。", "parameters": {"type": "object", "properties": {"order_number": {"type": "string"}}, "required": ["order_number"]}}},
    {"type": "function", "function": {"name": "get_work_orders", "description": "按 conversation_id 或 order_number 查询相关工单。", "parameters": {"type": "object", "properties": {"conversation_id": {"type": "string"}, "order_number": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "get_customer_context", "description": "按买家昵称聚合有限订单、消息和工单上下文。", "parameters": {"type": "object", "properties": {"buyer_nickname": {"type": "string"}, "limit": {"type": "integer", "maximum": 50}}, "required": ["buyer_nickname"]}}},
]

OUTPUT_KEYS = {"intent", "emotion", "summary", "evidence", "risk_level", "recommended_actions", "suggested_reply"}


class AgentOutput(BaseModel):
    """Single source of truth for the backwards-compatible agent JSON contract."""

    model_config = ConfigDict(extra="forbid")
    intent: str
    intent_major: str = Field(default="", max_length=80)
    intent_minor: str = Field(default="", max_length=120)
    emotion: str
    summary: str = Field(max_length=180)
    evidence: list[Any] = Field(max_length=6)
    risk_level: Literal["low", "medium", "high", "critical"]
    recommended_actions: list[str] = Field(default_factory=list, max_length=5)
    suggested_reply: str = Field(max_length=300)
    tools_used: list[str] = Field(default_factory=list, max_length=8)
    missing_information: list[str] = Field(default_factory=list, max_length=6)


class QuotaExhaustedError(RuntimeError):
    """Raised when the provider reports quota, billing, or balance exhaustion."""


@dataclass
class AgentResult:
    suggestion: str
    risk: dict[str, Any]
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    tool_calls: list[str]
    run_id: str
    structured_output_valid: bool = True
    model_output: dict[str, Any] | None = None
    errors: list[str] | None = None
    usage_records: list[dict[str, int]] | None = None
    finish_reason: str | None = None
    raw_final_content: str = ""
    response_format_mode: str = "json_schema"
    repair_used: bool = False
    hybrid_risk: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    task_id: str | None = None


class QwenProvider:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None, mock: bool | None = None):
        self.api_key = api_key or os.getenv("QWEN_API_KEY")
        self.base_url = (base_url or os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")).rstrip("/")
        self.model = model or os.getenv("QWEN_MODEL", "qwen3.7-plus")
        self.timeout = float(os.getenv("QWEN_TIMEOUT", "30"))
        self.temperature = float(os.getenv("QWEN_TEMPERATURE", "0.2"))
        self.free_only = os.getenv("QWEN_FREE_ONLY", "true").lower() in {"1", "true", "yes", "on"}
        configured_max_tokens = int(os.getenv("QWEN_MAX_TOKENS", "1024" if self.free_only else "1024"))
        self.max_tokens = min(configured_max_tokens, 1024 if self.free_only else configured_max_tokens)
        configured_rounds = int(os.getenv("QWEN_MAX_TOOL_ROUNDS", "4"))
        self.max_tool_rounds = min(configured_rounds, 4 if self.free_only else configured_rounds)
        self.tool_result_char_limit = 2000 if self.free_only else 12000
        self.enable_thinking = os.getenv("QWEN_ENABLE_THINKING", "false").lower() in {"1", "true", "yes", "on"}
        self.debug_dir = Path(os.getenv("QWEN_DEBUG_DIR", "data/generated/live_debug"))
        configured = os.getenv("AGENT_PROVIDER")
        self.provider = configured or ("mock" if os.getenv("QWEN_MOCK", "1") == "1" or not self.api_key else "qwen")
        if mock is not None:
            self.provider = "mock" if mock else "qwen"
        if self.provider == "qwen" and not self.api_key:
            raise RuntimeError("AGENT_PROVIDER=qwen requires QWEN_API_KEY")
        self.mock = self.provider == "mock"

    @staticmethod
    def _api_schema() -> dict[str, Any]:
        schema = json.loads(json.dumps(AgentOutput.model_json_schema()))
        def clean(node: Any) -> Any:
            if isinstance(node, dict):
                return {k: clean(v) for k, v in node.items() if k not in {"title", "default"}}
            if isinstance(node, list):
                return [clean(v) for v in node]
            return node
        schema = clean(schema)
        if isinstance(schema, dict) and isinstance(schema.get("properties"), dict):
            schema["required"] = list(schema["properties"].keys())
            schema["additionalProperties"] = False
        return schema

    @staticmethod
    def _normalize_intent_output(value: dict[str, Any]) -> dict[str, Any]:
        try:
            rows = [json.loads(line) for line in Path("data/generated/evaluation/manual_gold_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            taxonomy = IntentTaxonomy.from_rows(rows)
            mapped = taxonomy.map_text(str(value.get("intent", "")))
            if mapped:
                if not value.get("intent_major"): value["intent_major"] = mapped[0]
                if not value.get("intent_minor"): value["intent_minor"] = mapped[1]
                value["intent"] = mapped[0]
        except (OSError, json.JSONDecodeError):
            pass
        return value

    def _request(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], *, response_format: dict[str, Any] | None = None, stage: str = "tool") -> dict[str, Any]:
        payload = {"model": self.model, "messages": messages, "tools": tools, "tool_choice": "auto" if tools else "none", "temperature": self.temperature, "max_tokens": self.max_tokens, "enable_thinking": self.enable_thinking if stage == "tool" else False, "stream": False}
        if response_format is not None:
            payload["response_format"] = response_format
        request = urllib.request.Request(self.base_url + "/chat/completions", data=json.dumps(payload, ensure_ascii=False).encode(), headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
                self._write_debug(stage, payload, body, int(response.status), None)
                return body
        except Exception as exc:
            status = getattr(exc, "code", None)
            # Persist only a bounded transport error summary; never include headers or secrets.
            self._write_debug(stage, payload, {"error_type": type(exc).__name__, "error": str(exc)[:300]}, status, str(exc)[:300])
            message = str(exc).lower()
            if any(term in message for term in ("quota", "billing", "insufficient balance", "余额不足", "rate limit")):
                raise QuotaExhaustedError("Qwen quota/billing limit reported; live evaluation stopped") from exc
            raise

    def _write_debug(self, stage: str, payload: dict[str, Any], response: dict[str, Any], status: int | None, error: str | None) -> None:
        if self.provider != "qwen":
            return
        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            safe_payload = {"model": payload.get("model"), "max_tokens": payload.get("max_tokens"), "enable_thinking": payload.get("enable_thinking"), "stream": payload.get("stream", False), "tool_count": len(payload.get("tools", [])), "tool_choice": payload.get("tool_choice"), "response_format": payload.get("response_format")}
            choices = response.get("choices", []) if isinstance(response, dict) else []
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            summary = {"status": status, "error": error, "finish_reason": choices[0].get("finish_reason") if choices else None, "content": content, "content_chars": len(content), "tool_calls": choices[0].get("message", {}).get("tool_calls", []) if choices else [], "response_keys": sorted(response.keys()) if isinstance(response, dict) else []}
            path = self.debug_dir / f"{time.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}_{stage}.json"
            path.write_text(json.dumps({"request": safe_payload, "response": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _mock_suggested_reply(request_context: dict[str, Any], baseline_risk: dict[str, Any]) -> str:
        """Generate a deterministic, evidence-grounded reply for cached/demo mode."""
        messages = request_context.get("recent_messages", [])
        orders = request_context.get("orders", [])
        work_orders = request_context.get("work_orders", [])
        text = " ".join(str(item.get("message_text") or item.get("chat_content") or "") for item in messages if isinstance(item, dict))
        findings = baseline_risk.get("findings", [])
        adverse = next((item for item in work_orders if item.get("source_table") == "adverse_reaction_work_orders"), None)
        if adverse:
            number = adverse.get("work_order_number")
            symptom = adverse.get("symptom_description")
            detail = f"我已查到不良反应工单 {number}。" if number else "我已查到相关不良反应工单。"
            if symptom:
                detail += f"记录的情况是：{symptom}。"
            return detail + "先请您暂停使用并留意身体情况，我会马上转人工专员核实后续处理；如症状严重，请及时就医。"

        refund = next((item for item in work_orders if item.get("refund_issue_type") or item.get("transfer_status") or item.get("refund_amount_yuan")), None)
        if refund or "退款" in text or "退钱" in text:
            if refund:
                status = refund.get("transfer_status") or refund.get("work_order_status") or "待核实"
                amount = refund.get("refund_amount_yuan")
                amount_text = f"金额为 {amount} 元，" if amount else ""
                return f"我已查到您的退款记录，{amount_text}当前状态为“{status}”。我会继续帮您核对到账进度；如果页面状态与实际到账不一致，我会为您转人工跟进。"
            return "我会帮您进一步核实退款状态和到账记录，确认后给您明确回复，不先做无法保证的到账承诺。"

        logistics = next((item for item in work_orders if item.get("carrier") or item.get("problem_tracking_number") or item.get("issue_type")), None)
        order = orders[0] if orders else None
        tracking = (logistics or {}).get("problem_tracking_number") or (order or {}).get("tracking_number")
        if logistics or tracking or "物流" in text or "快递" in text:
            if tracking:
                carrier = (logistics or {}).get("carrier") or "物流"
                status = (logistics or {}).get("work_order_status") or (logistics or {}).get("resolution") or "查询中"
                return f"我已查到{carrier}单号 {tracking}，当前记录为“{status}”。我会继续帮您核对最新物流节点，并在有更新后及时回复。"
            return "我会帮您进一步核实物流单号和最新节点，确认后再给您明确的处理时间。"

        if order and (order.get("gift") or "赠品" in text):
            gift = order.get("gift") or "赠品信息待核实"
            return f"我已查到当前订单的赠品记录：{gift}。我会继续核对发货情况，确认后给您明确的补发或处理方案。"
        if findings:
            action = findings[0].get("recommended_action")
            if action:
                return f"我已结合当前会话和业务记录为您核对。{action}我会继续跟进并向您反馈明确结果。"
        return "我会帮您进一步核实相关订单、历史对话和售后记录，确认事实后再给您明确回复。"

    def run(self, request_context: dict[str, Any], baseline_risk: dict[str, Any], executor: dict[str, Callable[..., Any]]) -> tuple[Any, ...]:
        if self.mock:
            suggestion = self._mock_suggested_reply(request_context, baseline_risk)
            output = {"intent": "售后咨询", "emotion": "需关注" if baseline_risk["requires_human_review"] else "平稳", "summary": "已基于现有业务记录生成建议。", "evidence": baseline_risk["findings"], "risk_level": baseline_risk["level"], "recommended_actions": [f["recommended_action"] for f in baseline_risk["findings"]], "suggested_reply": suggestion}
            return suggestion, "mock", len(json.dumps(request_context, ensure_ascii=False)), 28, [], True, output, [], [], "stop", json.dumps(output, ensure_ascii=False), False

        schema_contract = json.dumps(self._api_schema(), ensure_ascii=False, separators=(",", ":"))
        system = load_prompt("stage_a_tools")
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps({"request": request_context, "baseline_risk": baseline_risk}, ensure_ascii=False)}]
        called: list[str] = []
        errors: list[str] = []
        prompt_tokens = completion_tokens = 0
        usage_records: list[dict[str, int]] = []
        final_output: dict[str, Any] = {}
        raw_final_content = ""
        finish_reason: str | None = None
        for _ in range(self.max_tool_rounds):
            body = self._request(messages, TOOL_SCHEMAS, stage="tool")
            usage = body.get("usage", {})
            prompt_tokens += usage.get("prompt_tokens", 0) or 0
            completion_tokens += usage.get("completion_tokens", 0) or 0
            usage_records.append({"input_tokens": int(usage.get("prompt_tokens", 0) or 0), "output_tokens": int(usage.get("completion_tokens", 0) or 0), "total_tokens": int(usage.get("total_tokens", (usage.get("prompt_tokens", 0) or 0) + (usage.get("completion_tokens", 0) or 0)) or 0)})
            message = body.get("choices", [{}])[0].get("message", {})
            finish_reason = body.get("choices", [{}])[0].get("finish_reason")
            tool_calls = message.get("tool_calls") or []
            if tool_calls:
                messages.append(message)
                for call in tool_calls[:4]:
                    name = call.get("function", {}).get("name", "")
                    if name not in executor:
                        errors.append(f"unknown_tool:{name}")
                        continue
                    args: dict[str, Any] = {}
                    try:
                        args = json.loads(call.get("function", {}).get("arguments", "{}"))
                        result = executor[name](**args)
                        called.append(name)
                        messages.append({"role": "tool", "tool_call_id": call.get("id", uuid.uuid4().hex), "name": name, "content": json.dumps(result, ensure_ascii=False, default=str)[:self.tool_result_char_limit]})
                    except Exception as exc:
                        # 原则 6 错误压缩：回注紧凑可自纠的错误 JSON，而非无信息量的占位符
                        errors.append(f"tool_error:{name}:{type(exc).__name__}")
                        compact = compact_tool_error(name, exc)
                        messages.append({"role": "tool", "tool_call_id": call.get("id", uuid.uuid4().hex), "name": name, "content": json.dumps(compact, ensure_ascii=False)})
                continue
            break
        evidence_messages = [m for m in messages if m.get("role") in {"tool", "user"}]
        synthesis_system = load_prompt("final_synthesis", schema_contract=schema_contract)
        synthesis_messages = [{"role": "system", "content": synthesis_system}, {"role": "user", "content": json.dumps({"request": request_context, "baseline_risk": baseline_risk, "retrieved_evidence": evidence_messages, "tools_used": called}, ensure_ascii=False)}]
        final_format = {"type": "json_schema", "json_schema": {"name": "agent_output", "schema": self._api_schema(), "strict": True}}
        final_body = self._request(synthesis_messages, [], response_format=final_format, stage="final_synthesis")
        final_usage = final_body.get("usage", {})
        prompt_tokens += final_usage.get("prompt_tokens", 0) or 0
        completion_tokens += final_usage.get("completion_tokens", 0) or 0
        usage_records.append({"input_tokens": int(final_usage.get("prompt_tokens", 0) or 0), "output_tokens": int(final_usage.get("completion_tokens", 0) or 0), "total_tokens": int(final_usage.get("total_tokens", (final_usage.get("prompt_tokens", 0) or 0) + (final_usage.get("completion_tokens", 0) or 0)) or 0)})
        final_choice = final_body.get("choices", [{}])[0]
        finish_reason = final_choice.get("finish_reason")
        raw_final_content = str(final_choice.get("message", {}).get("content", ""))
        final_output = self._parse_json(raw_final_content)
        final_output = self._normalize_intent_output(final_output)
        repair_used = False
        repair_eligible = self._repair_allowed(finish_reason, raw_final_content, final_output)
        if finish_reason == "length":
            errors.append("output_truncated")
        if repair_eligible:
            repair_used = True
            errors.append("json_schema_fallback_repair")
            repair_system = load_prompt("json_repair", schema_contract=schema_contract)
            repair_messages = [{"role": "system", "content": repair_system}, {"role": "user", "content": raw_final_content[: self.tool_result_char_limit]}]
            repair_body = self._request(repair_messages, [], response_format=final_format, stage="repair")
            repair_usage = repair_body.get("usage", {})
            prompt_tokens += repair_usage.get("prompt_tokens", 0) or 0
            completion_tokens += repair_usage.get("completion_tokens", 0) or 0
            usage_records.append({"input_tokens": int(repair_usage.get("prompt_tokens", 0) or 0), "output_tokens": int(repair_usage.get("completion_tokens", 0) or 0), "total_tokens": int(repair_usage.get("total_tokens", (repair_usage.get("prompt_tokens", 0) or 0) + (repair_usage.get("completion_tokens", 0) or 0)) or 0)})
            repair_content = str(repair_body.get("choices", [{}])[0].get("message", {}).get("content", ""))
            parsed_repair = self._parse_json(repair_content)
            if parsed_repair:
                final_output = self._normalize_intent_output(parsed_repair)
                errors.append("bounded_json_repair")
            else:
                errors.append("json_repair_failed")
        valid = self._validate_output(final_output)
        if not valid:
            errors.append("structured_output_invalid")
        suggestion = str(final_output.get("suggested_reply", "missing information"))
        return suggestion, "qwen", prompt_tokens, completion_tokens, called, valid, final_output, errors, usage_records, finish_reason, raw_final_content, repair_used

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        normalized = content.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`").lstrip("json").strip()
        try:
            value = json.loads(normalized)
        except json.JSONDecodeError:
            start, end = normalized.find("{"), normalized.rfind("}")
            if start < 0 or end <= start:
                return {}
            try:
                value = json.loads(normalized[start : end + 1])
            except json.JSONDecodeError:
                return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _validate_output(value: dict[str, Any]) -> bool:
        try:
            AgentOutput.model_validate(value)
            return True
        except ValidationError:
            return False

    @staticmethod
    def _repair_eligible(raw_content: str, parsed_output: dict[str, Any]) -> bool:
        """Allow one repair only when a substantive final response exists but fails validation."""
        text = raw_content.strip()
        return len(text) >= 20 and bool(parsed_output or "{" in text or "intent" in text.lower()) and not QwenProvider._validate_output(parsed_output)

    @staticmethod
    def _repair_allowed(finish_reason: str | None, raw_content: str, parsed_output: dict[str, Any]) -> bool:
        return finish_reason != "length" and QwenProvider._repair_eligible(raw_content, parsed_output)


class BeautyAgent:
    def __init__(self, db_path: Path, provider: QwenProvider | None = None):
        self.db_path = db_path
        self.tools = BusinessTools(db_path)
        self.context_engine = ContextEngine(db_path)
        self.provider = provider or QwenProvider()

    @staticmethod
    def _workflow_trace(request_context: dict[str, Any], context: dict[str, Any], risk: dict[str, Any], model_output: dict[str, Any] | None, calls: list[str]) -> dict[str, Any]:
        """Return a concise, UI-safe explanation of the Agent workflow."""
        labels = {
            "get_conversation": ("查询历史服务记录", "确认当前问题与历史沟通是否有关联"),
            "get_customer_context": ("查询客户与订单上下文", "核对客户、商品和关联订单"),
            "get_order": ("查询订单状态", "确认当前订单及履约事实"),
            "get_work_orders": ("查询物流、退款与服务工单", "核对售后状态、物流节点和历史处理记录"),
        }
        steps: list[dict[str, str]] = []
        for name in dict.fromkeys(calls):
            if name in labels:
                label, reason = labels[name]
                steps.append({"tool": name, "label": label, "reason": reason, "status": "completed"})
        recent = request_context.get("recent_messages", [])
        latest = ""
        if recent:
            latest = str(recent[-1].get("message_text") or recent[-1].get("chat_content") or "")
        need = str((model_output or {}).get("summary") or "")
        if not need or need.startswith("已基于"):
            if any(term in latest for term in ("退款", "退钱", "到账")):
                need = "消费者正在咨询退款状态或到账进度。"
            elif any(term in latest for term in ("物流", "快递", "签收", "发货")):
                need = "消费者正在咨询物流状态或配送异常。"
            elif any(term in latest for term in ("过敏", "刺痛", "发红", "瘙痒", "不适")):
                need = "消费者反馈使用后不适，需要安抚并核查售后处理。"
            elif "赠品" in latest:
                need = "消费者正在咨询赠品缺失或补发处理。"
            else:
                need = "根据当前消费者消息核对相关业务事实并给出可执行回复。"
        facts: list[str] = []
        if context.get("orders"):
            facts.append(f"已关联 {len(context['orders'])} 条订单记录")
        if context.get("work_orders"):
            facts.append(f"已核对 {len(context['work_orders'])} 条服务工单")
        if context.get("messages"):
            facts.append(f"已读取当前会话最近 {min(len(context['messages']), 6)} 条消息")
        if risk.get("findings"):
            facts.append(f"识别到 {len(risk['findings'])} 条风险依据")
        return {
            "customer_need": need,
            "latest_message": latest[:180],
            "tool_checks": steps,
            "evidence_summary": facts or ["暂未获得足够业务事实，需要进一步核实"],
            "risk_summary": {"level": risk.get("level", "low"), "reasons": [item.get("reason", "") for item in risk.get("findings", [])][:5]},
            "reply_basis": "；".join(facts) if facts else "未找到可确认的业务事实，回复将明确说明需要进一步核实",
        }

    def suggest(self, *, conversation_id: str | None = None, order_number: str | None = None, buyer_nickname: str | None = None) -> AgentResult:
        """原则 7：任务级全局状态全程落库（started → context_ready → synthesis_done → completed/failed）。"""
        started = time.perf_counter()
        task_id = str(uuid.uuid4())
        record_task(self.db_path, task_id, conversation_id, order_number, "started", {"buyer_nickname": buyer_nickname})
        try:
            result = self._suggest_inner(started, task_id, conversation_id=conversation_id, order_number=order_number, buyer_nickname=buyer_nickname)
            update_task(self.db_path, task_id, "completed", {"suggestion_chars": len(result.suggestion), "structured_output_valid": result.structured_output_valid}, run_id=result.run_id)
            result.task_id = task_id
            return result
        except Exception as exc:
            update_task(self.db_path, task_id, "failed", error=str(exc)[:300])
            raise

    def _suggest_inner(self, started: float, task_id: str, *, conversation_id: str | None = None, order_number: str | None = None, buyer_nickname: str | None = None) -> AgentResult:
        context: dict[str, Any] = {"messages": [], "orders": [], "work_orders": []}
        calls: list[str] = []
        agent_context = None
        if not (conversation_id or order_number or buyer_nickname):
            raise ValueError("conversation_id, order_number or buyer_nickname is required")
        # M12 Context Engine：任一入口自动推导完整业务上下文，按买家严格隔离
        if conversation_id:
            agent_context = self.context_engine.build(conversation_id=conversation_id)
            context = agent_context.raw_context
            calls.extend(["get_conversation", "get_customer_context", "get_work_orders"])
        elif buyer_nickname:
            agent_context = self.context_engine.build(buyer_nickname=buyer_nickname)
            context = agent_context.raw_context
            calls.append("get_customer_context")
        elif order_number:
            agent_context = self.context_engine.build(order_number=order_number)
            context = agent_context.raw_context
            calls.extend(["get_order", "get_work_orders"])
        if order_number and conversation_id:
            # 组合入口：会话上下文之上收敛到指定订单（与既有行为一致）
            order = self.tools.get_order(order_number)
            if order:
                context["orders"] = [order]
            context["work_orders"] = self.tools.get_work_orders(conversation_id, order_number)
            calls.extend(["get_order", "get_work_orders"])
        risk = assess_context(context) if (order_number and conversation_id) else (agent_context.risk or assess_context(context))
        compact = self.tools._project("customer_context", context)
        # 原则 5 上下文仲裁：按重要性分级进入 LLM 窗口，替代 FIFO 截断
        recent_messages, arbitration = arbitrate_messages(compact.get("messages", []), max_messages=6)
        orders, order_arbitration = arbitrate_orders(compact.get("orders", []), order_number, recent_messages, max_orders=3)
        request_context = {"conversation_id": conversation_id, "order_number": order_number, "buyer_nickname": buyer_nickname, "message_count": len(context.get("messages", [])), "order_count": len(context.get("orders", [])), "work_order_count": len(context.get("work_orders", [])), "recent_messages": recent_messages, "orders": orders, "work_orders": compact.get("work_orders", [])[:6], "context_arbitration": {"messages": arbitration, "orders": order_arbitration}}
        if agent_context is not None:
            # M12：统一上下文随请求下发（客户/会话/服务历史/风险/可用工具），模型不再缺业务背景
            engine_payload = agent_context.as_dict()
            request_context["customer"] = engine_payload.get("customer", {})
            request_context["session"] = engine_payload.get("session", {})
            request_context["service_history"] = engine_payload.get("service_history", {})
            request_context["risk_context"] = engine_payload.get("risk", {})
            request_context["available_tools"] = engine_payload.get("available_tools", [])
        update_task(self.db_path, task_id, "context_ready", {"message_count": request_context["message_count"], "order_count": request_context["order_count"], "work_order_count": request_context["work_order_count"], "risk_level": risk.get("level"), "arbitration": request_context["context_arbitration"]})
        executor = self.tools.list_tools(compact=True)
        suggestion, provider_name, input_tokens, output_tokens, model_calls, valid, model_output, errors, usage_records, finish_reason, raw_final_content, repair_used = self.provider.run(request_context, risk, executor)
        calls.extend(model_calls)
        latency_ms = int((time.perf_counter() - started) * 1000)
        run_id = str(uuid.uuid4())
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS agent_runs (run_id TEXT PRIMARY KEY, provider TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER, latency_ms INTEGER, tool_calls_json TEXT, risk_level TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            conn.execute("INSERT INTO agent_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", (run_id, provider_name, self.provider.model, input_tokens, output_tokens, latency_ms, json.dumps(calls, ensure_ascii=False), risk["level"]))
            conn.commit()
        update_task(self.db_path, task_id, "synthesis_done", {"provider": provider_name, "input_tokens": input_tokens, "output_tokens": output_tokens, "latency_ms": latency_ms, "tool_calls": calls, "structured_output_valid": valid})
        model_risk = (model_output or {}).get("risk_level")
        if model_output is not None:
            model_output.setdefault("tools_used", list(dict.fromkeys(calls)))
        hybrid = hybrid_risk(context, model_risk, risk.get("level"), risk.get("findings", []))
        workflow = self._workflow_trace(request_context, context, risk, model_output, calls)
        return AgentResult(suggestion, risk, provider_name, self.provider.model, input_tokens, output_tokens, latency_ms, calls, run_id, valid, model_output, errors, usage_records, finish_reason, raw_final_content, "json_schema", repair_used, hybrid, workflow)
