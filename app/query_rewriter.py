"""M18.1 Query Rewrite：检索前查询改写。

用户口语与知识库用词存在词汇鸿沟（"用了脸疼" vs 知识库的"刺痛/过敏/不适"），
直接检索会失败。规则版改写：命中同义词映射时把标准词附加到查询后
（不改写原文，原语义保留），再进入混合检索。

接入 qwen live 后可替换为 LLM 改写，本模块保留为无网络兜底。
"""
from __future__ import annotations

from typing import Any

# 口语/俗称 → 知识库标准词（ longest-match 优先；词表按演示场景维护）
SYNONYM_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("脸疼", ("刺痛", "过敏", "不良反应")),
    ("脸痛", ("刺痛", "过敏", "不良反应")),
    ("脸上疼", ("刺痛", "过敏", "不良反应")),
    ("烂脸", ("过敏", "不良反应")),
    ("起疹", ("过敏", "不良反应")),
    ("红肿", ("发红", "过敏")),
    ("脸上痒", ("瘙痒",)),
    ("皮肤痒", ("瘙痒",)),
    ("刺激", ("刺痛", "不适")),
    ("辣眼睛", ("刺痛",)),
    ("没效果", ("功效", "使用方法")),
    ("不管用", ("功效", "使用方法")),
    ("咋用", ("使用方法",)),
    ("咋保存", ("保存方法",)),
    ("能退不", ("退货条件",)),
)


def rewrite_query(query: str) -> dict[str, Any]:
    """返回 {"original", "rewritten", "added_terms"}；无命中时 rewritten 等于 original。"""
    original = str(query or "").strip()
    added: list[str] = []
    for spoken, standard_terms in SYNONYM_RULES:
        if spoken in original:
            for term in standard_terms:
                if term not in added:
                    added.append(term)
    rewritten = f"{original}{' ' + ' '.join(added) if added else ''}".strip()
    return {"original": original, "rewritten": rewritten, "added_terms": added}
