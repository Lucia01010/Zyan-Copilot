"""12-Factor 原则 6：错误压缩器。

把工具执行异常提炼为紧凑、对 LLM 友好的结构化 JSON，使其能据此自我纠正，
而不是把冗长堆栈或无信息量的 {"error": "tool failed"} 回注上下文。
字段遵循 {error_summary, error_type, message, offending_parameter?, suggestion}，
省略值为 None 的字段以节省 token。
"""
from __future__ import annotations

import json
import re
from typing import Any

_MAX_MESSAGE_CHARS = 200

_UNEXPECTED_KW = re.compile(r"unexpected keyword argument '([^']+)'")
_MISSING_ARG = re.compile(r"missing (?:\d+ )?required (?:positional |keyword-only )?argument: '([^']+)'")


def _offending_parameter(exc: Exception) -> str | None:
    text = str(exc)
    match = _UNEXPECTED_KW.search(text) or _MISSING_ARG.search(text)
    if match:
        return match.group(1)
    if isinstance(exc, KeyError):
        name = str(exc).strip("'\"")
        return name or None
    return None


def _suggestion(tool_name: str, offending: str | None, exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return "工具参数 arguments 不是合法 JSON object，请严格按工具 schema 输出 JSON 后重试。"
    if offending and _UNEXPECTED_KW.search(str(exc)):
        return f"参数 '{offending}' 不在工具 '{tool_name}' 的 schema 中，请改用工具定义的参数名后重试。"
    if offending and _MISSING_ARG.search(str(exc)):
        return f"缺少必填参数 '{offending}'，请补齐后重试。"
    if isinstance(exc, KeyError):
        return f"返回数据缺少字段 '{offending}'，请如实告知用户需进一步核实，不要编造。"
    return "请检查参数是否符合工具 schema；若持续失败，请如实告知用户会进一步核实，不要编造数据。"


def compact_tool_error(tool_name: str, exc: Exception) -> dict[str, str]:
    error_type = type(exc).__name__
    raw_message = str(exc).strip()
    message = raw_message.splitlines()[0][:_MAX_MESSAGE_CHARS] if raw_message else error_type
    offending = _offending_parameter(exc)
    compact: dict[str, str] = {
        "error_summary": f"工具 '{tool_name}' 调用失败。",
        "error_type": error_type,
        "message": message,
        "suggestion": _suggestion(tool_name, offending, exc),
    }
    if offending:
        compact["offending_parameter"] = offending
    return compact
