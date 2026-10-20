"""Grounded quick actions for the Zhiyan Copilot plugin.

The registry is the single allowlist shared by recommendation and execution.
It never fabricates a result: tools return NOT_FOUND when the instance data
does not contain the requested business record.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from app.business_tools import BusinessTools
from app.error_compactor import compact_tool_error
from app.risk_engine import assess_context


@dataclass(frozen=True)
class ActionDefinition:
    """M14 Action Registry：每个行动的自描述元数据。

    description / trigger_examples / required_context 供 Planner 规划与
    未来 LLM Planner 提示词使用；tool_name 是 Router 的唯一执行映射。
    """

    action_id: str
    display_name: str
    tool_name: str
    scenes: tuple[str, ...]
    source: str
    description: str = ""
    trigger_examples: tuple[str, ...] = ()
    required_context: tuple[str, ...] = ("session_id",)

    @property
    def input_schema(self) -> dict[str, Any]:
        """M19 Tool Governance：显式输入契约（由 required_context 推导，免逐条维护）。"""
        return {"type": "object", "required": list(self.required_context), "properties": {name: {"type": "string"} for name in self.required_context}}


ACTION_DEFINITIONS: tuple[ActionDefinition, ...] = (
    ActionDefinition("check_order", "查看订单信息", "get_order_info", ("订单", "普通咨询", "赠品"), "orders", "查询当前客户关联订单与商品信息", ("帮我查一下订单", "这个客户买了什么", "订单里的商品是什么")),
    ActionDefinition("check_logistics", "查看物流信息", "get_logistics_info", ("物流", "未收到", "发货"), "orders + logistics_work_orders", "查询订单物流承运商、单号与配送状态", ("物流到哪了", "快递怎么还没收到", "发货了吗")),
    ActionDefinition("check_refund", "查看退款状态", "get_refund_status", ("退款", "到账", "售后"), "after_sales_return_work_orders + offline_payment_work_orders", "查询退款单处理状态与到账进度", ("退款什么时候到账", "钱退了吗", "退款怎么关闭了")),
    ActionDefinition("check_payment", "查看打款状态", "get_payment_status", ("线下打款", "退款", "到账"), "offline_payment_work_orders", "查询线下打款（支付宝/银行卡）处理状态", ("打款到了吗", "支付宝转账进度")),
    ActionDefinition("check_return", "查看退货进度", "get_return_status", ("退货", "退款"), "after_sales_return_work_orders", "查询退货流程与仓库签收进度", ("退货到哪一步了", "仓库签收了吗")),
    ActionDefinition("check_replacement", "查看换货状态", "get_replacement_status", ("换货", "补发"), "replacement_work_orders", "查询换货与补发单处理状态", ("换货发出了吗", "补发单号是多少")),
    ActionDefinition("check_ticket", "查看售后工单", "get_ticket_status", ("售后", "工单", "投诉"), "work_orders", "查询售后工单当前处理状态", ("工单处理得怎么样了", "售后进度如何")),
    ActionDefinition("check_adverse_reaction", "查看不良反应记录", "get_adverse_reaction_record", ("不良反应", "过敏", "发红", "瘙痒", "刺痛"), "adverse_reaction_work_orders", "查询不良反应登记与处理记录", ("客户说过敏了", "不良反应登记了吗", "用后发红刺痛怎么处理")),
    ActionDefinition("summarize_customer_history", "查看历史沟通", "summarize_customer_history", ("历史", "投诉", "重复进线", "不良反应"), "customer_context", "汇总客户历史沟通、工单与服务承诺，输出历史服务摘要", ("这个客户之前遇到过什么问题", "查看历史沟通", "客服之前承诺过什么"), ("session_id", "buyer_nickname（由会话锚定）")),
    ActionDefinition("check_service_promises", "查看历史服务承诺", "get_service_promises", ("承诺", "补发", "回访", "赠品"), "chat_messages", "核对客服历史承诺与跟进记录", ("之前承诺的赠品发了吗", "客服答应的回访做了吗")),
    ActionDefinition("assess_customer_risk", "分析客户风险", "get_customer_context", ("风险", "情绪", "投诉"), "risk_engine", "基于客户全量上下文评估风险等级与命中规则", ("这个客户风险为什么这么高", "客户情绪怎么样", "这个客户为什么投诉"), ("session_id", "buyer_nickname（由会话锚定）")),
    ActionDefinition("search_knowledge_base", "查询业务知识库", "search_knowledge", ("产品知识", "售后规则", "客服规范"), "knowledge_base", "检索产品知识、售后规则与客服规范等通用政策知识；只回答通用知识，不包含任何具体订单事实", ("修护精华液怎么使用", "退货需要满足什么条件", "产品保质期多久"), ("question_text（用户问题原文）",)),
)

REGISTRY_BY_ID = {item.action_id: item for item in ACTION_DEFINITIONS}
TOOL_BY_ACTION = {item.action_id: item.tool_name for item in ACTION_DEFINITIONS}


def registry_catalog() -> list[dict[str, Any]]:
    """输出 Registry 目录（action_id/描述/触发示例/所需上下文/工具映射）。

    Planner 与人机界面共用同一份元数据，保证规划依据可审计。
    """
    return [{"action_id": item.action_id, "display_name": item.display_name, "description": item.description, "trigger_examples": list(item.trigger_examples), "required_context": list(item.required_context), "input_schema": item.input_schema, "tool": item.tool_name, "source": item.source} for item in ACTION_DEFINITIONS]


def _conversation_text(tools: BusinessTools, session_id: str) -> str:
    return " ".join(str(row.get("message_text") or row.get("chat_content") or "") for row in tools.get_conversation(session_id)[-12:])


def recommend_actions(tools: BusinessTools, session_id: str) -> list[dict[str, Any]]:
    """Return 1-4 high-signal actions from current instance context."""
    text = _conversation_text(tools, session_id)
    ranked: list[tuple[int, ActionDefinition, str]] = []
    rules = (
        ("check_adverse_reaction", ("过敏", "发红", "瘙痒", "刺痛", "不适"), "需要核对不良反应登记和处理状态"),
        ("check_logistics", ("物流", "快递", "没收到", "未收到", "发货", "签收"), "消费者正在询问配送或签收状态"),
        ("check_refund", ("退款", "退钱", "到账", "钱退", "售后单关闭"), "消费者正在询问退款或到账进度"),
        ("check_payment", ("打款", "支付宝", "线下"), "当前对话涉及线下打款状态"),
        ("check_return", ("退货", "退回", "仓库签收"), "需要核对退货和售后进度"),
        ("check_replacement", ("换货", "补发", "漏发", "少件"), "需要核对换货或补发状态"),
        ("check_service_promises", ("赠品", "承诺", "回访"), "需要核对历史服务承诺"),
        ("summarize_customer_history", ("投诉", "重复", "再次进线", "历史"), "需要回看历史沟通"),
    )
    for action_id, terms, reason in rules:
        if any(term in text for term in terms):
            ranked.append((len([term for term in terms if term in text]), REGISTRY_BY_ID[action_id], reason))
    if not ranked:
        ranked.append((1, REGISTRY_BY_ID["check_order"], "先核对当前订单和商品上下文"))
    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:3]
    if len(selected) < 2 and selected[0][1].action_id not in {"summarize_customer_history", "check_order"}:
        selected.append((0, REGISTRY_BY_ID["summarize_customer_history"], "必要时回看历史服务记录"))
    return [{"action_id": definition.action_id, "label": definition.display_name, "reason": reason, "priority": "primary" if index == 0 else "secondary", "tool_name": definition.tool_name, "available": True, "source": definition.source} for index, (_, definition, reason) in enumerate(selected[:4])]


def _execute_knowledge_action(query: str, session_id: str, store: Any) -> dict[str, Any]:
    """search_knowledge_base：M15 RAG 检索，只返回通用知识切片，不触碰订单数据。"""
    base = {"action_id": "search_knowledge_base", "tool_name": "search_knowledge", "session_id": session_id, "source": "knowledge_base"}
    try:
        matches = store.search_dicts(str(query), top_k=3)
    except Exception as exc:
        return {"status": "ERROR", "data": {}, "error": compact_tool_error("search_knowledge", exc), **base}
    if not matches:
        return {"status": "NOT_FOUND", "data": {"query": query, "matches": []}, **base}
    return {"status": "OK", "data": {"query": query, "matches": matches}, **base}


def _execute_risk_action(tools: BusinessTools, session_id: str) -> dict[str, Any]:
    """assess_customer_risk：由会话锚定买家，客户上下文 + 风险引擎评估。"""
    messages = tools.get_conversation(session_id)
    buyer = messages[0].get("buyer_nickname") if messages else None
    base = {"action_id": "assess_customer_risk", "tool_name": "get_customer_context", "session_id": session_id, "source": "risk_engine"}
    if not buyer:
        return {"status": "NOT_FOUND", "data": {}, **base}
    risk = assess_context(tools.get_customer_context(str(buyer)))
    return {"status": "OK", "data": {"buyer_nickname": buyer, "level": risk.get("level", "low"), "requires_human_review": risk.get("requires_human_review", False), "findings": risk.get("findings", [])}, **base}


def execute_action(tools: BusinessTools, action_id: str, session_id: str) -> dict[str, Any]:
    definition = REGISTRY_BY_ID.get(action_id)
    if definition is None:
        raise KeyError(f"unknown action: {action_id}")
    try:
        if action_id == "assess_customer_risk":
            return _execute_risk_action(tools, session_id)
        tool: Callable[..., Any] = getattr(tools, definition.tool_name)
        result = tool(session_id)
    except Exception as exc:
        # 原则 6 错误压缩：结构化 ERROR 载荷随响应返回供审计/自纠，不向上抛裸异常
        return {"status": "ERROR", "data": {}, "error": compact_tool_error(definition.tool_name, exc), "action_id": action_id, "tool_name": definition.tool_name, "session_id": session_id}
    return {**result, "action_id": action_id, "tool_name": definition.tool_name, "session_id": session_id}


def _format_history_summary(data: dict[str, Any]) -> str:
    """规则化历史服务总结：沟通次数、核心问题、时间线、承诺、当前建议。

    mock 模式下不调用 LLM，基于关键词提取与风险规则生成结构化摘要；
    接入 qwen live 后可替换为 LLM 总结，函数签名不变。
    """
    if not data:
        return "暂无历史服务记录。"
    buyer = data.get("buyer_nickname") or "该客户"
    session_count = data.get("session_count", 0)
    message_count = data.get("message_count", 0)
    messages = data.get("messages") or []
    work_orders = data.get("work_orders") or []
    promises = data.get("promises") or []
    if not messages:
        return "暂无历史服务记录。"

    # 核心问题：关键词匹配
    problem_keywords = [
        ("过敏/不良反应", ("过敏", "发红", "瘙痒", "刺痛", "不良反应", "不适")),
        ("物流问题", ("物流", "快递", "没收到", "未收到", "发货", "签收")),
        ("退款/打款", ("退款", "退钱", "到账", "打款", "支付宝")),
        ("退货/换货", ("退货", "退回", "换货", "补发", "漏发", "少件")),
        ("赠品问题", ("赠品", "礼物", "没送")),
        ("投诉/不满", ("投诉", "不满", "差评", "态度")),
    ]
    all_text = " ".join(str(m.get("message_text") or "") for m in messages)
    core_problems = [label for label, terms in problem_keywords if any(t in all_text for t in terms)]

    # 工单问题
    if work_orders:
        wo_types = set()
        for wo in work_orders:
            t = wo.get("work_order_type") or wo.get("source_table") or ""
            if "adverse" in t or "reaction" in t:
                wo_types.add("不良反应工单")
            elif "logistics" in t:
                wo_types.add("物流工单")
            elif "return" in t or "refund" in t:
                wo_types.add("退换货工单")
            elif "replacement" in t:
                wo_types.add("补换货工单")
            elif "payment" in t:
                wo_types.add("打款工单")
            elif t:
                wo_types.add("售后工单")
        if wo_types:
            core_problems.extend(list(wo_types))
    if not core_problems:
        core_problems = ["常规咨询"]

    # 时间线：取最近 5 条，按时间正序
    timeline_msgs = sorted(messages, key=lambda m: (str(m.get("sent_at") or ""), str(m.get("message_sequence") or "")))[-5:]
    timeline = []
    for msg in timeline_msgs:
        role = msg.get("role") or "用户"
        text = str(msg.get("message_text") or "")[:80]
        ts = str(msg.get("sent_at") or "")[:16]
        timeline.append(f"  {ts} {role}：{text}")

    # 历史承诺
    promise_texts = []
    for p in promises[-3:]:
        role = p.get("role") or "客服"
        text = str(p.get("message_text") or "")[:80]
        promise_texts.append(f"  {role}：{text}")

    # 当前建议
    advice_parts = []
    if "过敏/不良反应" in core_problems:
        advice_parts.append("确认不良反应登记状态，必要时升级处理")
    if "物流问题" in core_problems:
        advice_parts.append("核查物流轨迹，主动同步配送进展")
    if "退款/打款" in core_problems or "退货/换货" in core_problems:
        advice_parts.append("跟进退换货/退款流程，确认是否已到账")
    if "投诉/不满" in core_problems:
        advice_parts.append("安抚情绪，优先处理核心诉求")
    if promises:
        advice_parts.append("核查历史承诺是否已兑现")
    if not advice_parts:
        advice_parts.append("基于当前会话诉求主动跟进")

    lines = [
        f"【历史服务摘要】客户 {buyer}，共 {session_count} 个会话、{message_count} 条沟通记录。",
        f"核心问题：{'、'.join(core_problems)}",
        "时间线摘要：",
        "\n".join(timeline),
    ]
    if promise_texts:
        lines.append("历史承诺：")
        lines.extend(promise_texts)
    else:
        lines.append("历史承诺：暂未识别到明确承诺。")
    lines.append(f"当前建议：{'；'.join(advice_parts)}。")
    return "\n".join(lines)


def format_action_result(result: dict[str, Any]) -> str:
    if result.get("status") == "ERROR":
        return "业务查询服务暂时异常，我会记录问题并尽快核实后给您答复。"
    if result.get("status") != "OK":
        if result.get("action_id") == "summarize_customer_history":
            return "暂无历史服务记录。"
        if result.get("action_id") == "assess_customer_risk":
            return "当前会话未关联客户，无法进行风险分析。"
        if result.get("action_id") == "search_knowledge_base":
            return "知识库中暂未找到该问题的相关说明，建议联系人工客服按售后流程核实处理。"
        return "未找到相关业务记录，我会帮您进一步核实。"
    data = result.get("data") or {}
    action_id = result.get("action_id")
    if action_id == "search_knowledge_base":
        matches = data.get("matches") or []
        if not matches:
            return "知识库中暂未找到该问题的相关说明，建议联系人工客服按售后流程核实处理。"
        top = matches[0]
        citations = "；".join(f"《{item.get('doc_title')}·{item.get('section')}》" for item in matches)
        return f"{top.get('text', '').strip()}\n参考来源：{citations}"
    if action_id == "assess_customer_risk":
        buyer = data.get("buyer_nickname") or "该客户"
        findings = data.get("findings") or []
        level = _RISK_LABELS.get(data.get("level", "low"), "低")
        if findings:
            return f"客户 {buyer} 当前风险等级为“{level}”，主要依据：" + "；".join(item.get("reason", "") for item in findings[:3]) + "。可在知妍·洞察查看完整风险详情。"
        return f"客户 {buyer} 当前未命中明确风险规则，暂无高风险信号。"
    if action_id == "check_logistics":
        rows = data.get("work_orders") or []
        orders = data.get("orders") or []
        row = rows[0] if rows else {}
        order = orders[0] if orders else {}
        carrier = row.get("carrier") or ""
        tracking = row.get("problem_tracking_number") or order.get("tracking_number")
        status = row.get("work_order_status") or row.get("resolution") or order.get("order_status") or "已记录"
        parts = ["当前订单物流信息已查到"]
        if carrier: parts.append(f"承运商：{carrier}")
        if tracking: parts.append(f"物流单号：{tracking}")
        parts.append(f"当前状态：{status}")
        parts.append("当前实例数据未提供更详细的实时轨迹。")
        return "；".join(parts) + "。"
    if action_id in {"check_refund", "check_payment", "check_return", "check_replacement", "check_ticket", "check_adverse_reaction"}:
        rows = data if isinstance(data, list) else data.get("work_orders") or []
        row = rows[0] if rows else {}
        number = row.get("work_order_number")
        status = row.get("transfer_status") or row.get("work_order_status") or row.get("task_status") or "待核实"
        label = {"check_refund": "退款", "check_payment": "打款", "check_return": "退货", "check_replacement": "补发/换货", "check_ticket": "售后工单", "check_adverse_reaction": "不良反应记录"}[action_id]
        return f"当前{label}记录状态为“{status}”" + (f"，记录编号为 {number}" if number else "") + "。"
    if action_id == "check_order":
        rows = data if isinstance(data, list) else []
        return f"当前客户共有 {len(rows)} 条订单记录，已为您列出相关订单信息。"
    if action_id == "summarize_customer_history":
        return _format_history_summary(data)
    if action_id == "check_service_promises":
        rows = data if isinstance(data, list) else []
        return f"已查到 {len(rows)} 条包含承诺或服务跟进信息的沟通记录。"
    return "已完成查询。"


CAPABILITY_RESPONSE = """我是知妍·伴答，是客服工作台中的AI助手。
我可以帮助您：
1. 查询订单信息
2. 查看物流状态
3. 查询退款/打款进度
4. 查看售后工单
5. 分析客户情绪和风险
6. 生成客服建议回复
您可以直接提问，或者点击下方建议行动。"""

UNKNOWN_REPLY = "这个问题我暂时无法直接回答。您可以询问订单、物流、退款、售后工单等业务问题，也可以让我分析客户风险，或点击下方建议行动。"

CAPABILITY_TERMS = ("你能做什么", "你可以做什么", "能做什么", "你有什么功能", "有哪些功能", "有什么功能", "介绍一下自己", "介绍下自己", "你可以帮助我什么", "你能帮助我什么", "你能帮我什么", "你会什么", "你能干什么", "你是谁", "你有什么用")
RISK_TERMS = ("风险", "情绪", "高危", "紧急")
# M15：客户正在发生的疑似不良反应属于业务事件，优先查业务记录（安全优先），不走 RAG
# M18.1：补充口语表述（脸疼/脸痛/红肿等）与标准术语同等优先级
ADVERSE_EVENT_TERMS = ("过敏", "发红", "瘙痒", "刺痛", "不良反应", "起疹", "烂脸", "脸疼", "脸痛", "脸上疼", "脸上痒", "皮肤痒", "红肿", "辣眼睛")
# M15：具体订单/工单事实查询信号——这些问题必须走 Business Tool，RAG 不得覆盖真实订单数据
ORDER_NUMBER_PATTERN = re.compile(r"[a-zA-Z]{2,}\d{6,}|\d{10,}")
STATUS_QUERY_TERMS = ("到账", "进度", "状态", "单号", "查一下", "查询", "帮我查", "查下", "到哪", "到了吗", "到了没", "发货了吗", "签收了吗", "退了吗", "退款了吗", "什么时候发", "催一下", "我的订单", "这个订单", "该订单")
# M15：通用知识类问题（产品使用/政策规则/规范）——走 RAG 知识库
KNOWLEDGE_TERMS = ("怎么用", "怎么使用", "如何使用", "如何用", "使用方法", "用法", "成分", "功效", "保质期", "怎么保存", "保存方法", "肤质", "适合", "适用", "注意事项", "规则", "政策", "规定", "条件", "标准", "规范", "可以退吗", "能不能退", "可以退", "多久", "流程", "如何处理", "怎么处理", "搭配", "步骤")
BUSINESS_ROUTES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check_adverse_reaction", ("过敏", "发红", "瘙痒", "刺痛", "不良反应", "起疹", "烂脸", "脸疼", "脸痛", "脸上痒", "皮肤痒", "红肿", "辣眼睛")),
    ("check_logistics", ("物流", "快递", "发货", "收到", "签收")),
    ("check_refund", ("退款", "退钱", "到账")),
    ("check_payment", ("打款", "支付宝", "线下")),
    ("check_return", ("退货", "退回")),
    ("check_replacement", ("换货", "补发", "漏发", "少件")),
    ("check_ticket", ("工单", "售后", "投诉")),
    ("check_order", ("订单", "赠品", "商品")),
)
_BUSINESS_TERMS = tuple(term for _, terms in BUSINESS_ROUTES for term in terms)
_RISK_LABELS = {"low": "低", "medium": "中", "high": "高", "critical": "紧急"}


# 知识-成分语境信号：出现这些词说明在问产品属性，即使同时有"过敏"也是知识查询而非业务事件
_PRODUCT_KNOWLEDGE_SIGNALS = ("成分", "配方", "致敏", "过敏原", "会不会过敏", "可能过敏", "会不会刺激", "禁忌", "不能用")


def classify_copilot_intent(text: str) -> str:
    """规则化意图分类：能力咨询 / 业务查询 / 知识查询 / 风险询问 / 无法识别。

    优先级：能力咨询 → 具体业务事实 → 通用知识 → 一般业务 → 风险 → 未知。

    特殊处理：当文本同时包含不良反应术语（过敏/刺痛等）和产品知识信号
    （成分/致敏/配方等）时，归为 knowledge_query——客服在问"这款精华的
    致敏成分是什么"，而不是在描述"客户用后过敏了"。
    """
    normalized = "".join(str(text or "").lower().split())
    if not normalized:
        return "unknown"
    if any(term in normalized for term in CAPABILITY_TERMS):
        return "capability_question"
    # 成分/致敏相关的"过敏"属于产品知识查询，不是业务事件
    has_adverse = any(term in normalized for term in ADVERSE_EVENT_TERMS)
    has_product_knowledge = any(term in normalized for term in _PRODUCT_KNOWLEDGE_SIGNALS)
    if has_adverse and has_product_knowledge:
        return "knowledge_query"
    if has_adverse:
        return "business_query"
    if ORDER_NUMBER_PATTERN.search(normalized) or any(term in normalized for term in STATUS_QUERY_TERMS):
        return "business_query"
    if any(term in normalized for term in KNOWLEDGE_TERMS + ("推荐", "选品", "买什么", "选什么", "敏感肌", "干皮", "油皮")):
        return "knowledge_query"
    if any(term in normalized for term in _BUSINESS_TERMS):
        return "business_query"
    if any(term in normalized for term in RISK_TERMS):
        return "risk_query"
    return "unknown"


def handle_copilot_chat(tools: BusinessTools, session_id: str, text: str, knowledge_store: Any = None) -> dict[str, Any]:
    """原则 5 意图先行 + M14 Planner/Router + M15 RAG：先分类再规划，只有需要工具的意图才进入 Router。

    能力咨询直接返回固定介绍；未知意图诚实说明能力边界；
    禁止把任何盲目的 actions[0] 兜底当作普通回答。
    knowledge_store 缺省使用进程级默认知识库（knowledge/ 目录）。
    """
    intent = classify_copilot_intent(text)
    if intent == "capability_question":
        return {"intent": intent, "message": CAPABILITY_RESPONSE, "tools_used": [], "evidence": [], "plan_mode": "none", "plan": []}
    if intent == "unknown":
        return {"intent": intent, "message": UNKNOWN_REPLY, "tools_used": [], "evidence": [], "plan_mode": "none", "plan": []}
    # M14：业务/风险/知识意图交由 Planner 规划，Action Router 执行（延迟导入避免循环依赖）
    from app.planner import build_plan, run_plan

    plan = build_plan(text, intent)
    route = run_plan(tools, session_id, plan, message=text, store=knowledge_store)
    if not route["results"]:
        return {"intent": intent, "message": UNKNOWN_REPLY, "tools_used": [], "evidence": [], "plan_mode": "none", "plan": []}
    return {"intent": intent, "message": route["message"], "tools_used": route["tools_used"], "evidence": route["evidence"], "plan_mode": plan["mode"], "plan": plan["steps"]}
