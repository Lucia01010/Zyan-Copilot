"""M15 RAG Knowledge Brain + M17/M18 工程化升级。

M17 Knowledge Pipeline：文件/数据库/API 经统一 KnowledgeLoader 转为
Document（page_content + metadata）→ 切片 → embedding → SQLite 向量库；
metadata 随切片持久化，回答可追溯"结论来自哪里"。

M18 Retrieval Intelligence：查询改写（口语→标准词）→ 粗排召回（宽阈值池）
→ 多信号精排（语义 + 标题 + 关键词覆盖混合通道）→ 阈值过滤 → top_k。

设计约束（与比赛演示环境一致）：
- 纯标准库实现，无网络依赖：embedding 使用确定性的字符 n-gram 哈希向量，
  维度固定、可持久化、跨进程一致；未来可在 embed() 后接远程/本地模型而
  不改变 KnowledgeStore 的接口（ingest/search 签名不变）。
- 知识库只存通用产品知识与政策规范，从不存储客户/订单数据；检索结果
  永远不会覆盖业务工具返回的订单事实。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from app.knowledge_loader import Document, KnowledgeLoader
from app.query_rewriter import rewrite_query

EMBED_DIM = 512
SCORE_THRESHOLD = 0.12
# M18.3：粗排召回池（宽阈值候选上限）与关键词通道权重；精排在池内多信号重排
RECALL_POOL = 20
RECALL_THRESHOLD_RATIO = 0.5
KEYWORD_WEIGHT = 0.5

_CJK = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD = re.compile(r"[a-z0-9]+")


def _features(text: str) -> list[str]:
    """中文字符 unigram+bigram 与 ASCII 词（小写）构成的特征。"""
    normalized = re.sub(r"\s+", "", str(text or "").lower())
    feats: list[str] = []
    cjk = _CJK.findall(normalized)
    feats.extend(cjk)
    feats.extend(cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1))
    feats.extend(_ASCII_WORD.findall(normalized))
    return feats


def embed(text: str) -> list[float]:
    """确定性哈希 embedding：特征经 md5 哈希到固定维度并带符号，最后 L2 归一化。"""
    vector = [0.0] * EMBED_DIM
    for feat in _features(text):
        digest = hashlib.md5(feat.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBED_DIM
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        vector = [value / norm for value in vector]
    return vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _content_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    domain: str
    doc_title: str
    section: str
    text: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"chunk_id": self.chunk_id, "domain": self.domain, "doc_title": self.doc_title, "section": self.section, "text": self.text, "score": round(self.score, 4), "metadata": dict(self.metadata)}


class KnowledgeRetriever:
    """M18：独立检索器——不绑定具体存储，候选来自注入的 candidate_fn。

    管线：Query Rewrite → 粗排召回（宽阈值池）→ 多信号精排（语义 + 标题
    + 关键词覆盖混合通道）→ 阈值过滤。未来替换向量库/远程 embedding 时
    只需替换 candidate_fn，检索智能层不变。
    """

    def __init__(self, candidate_fn: Callable[[str, str | None, int, float], list[dict[str, Any]]]):
        self._candidate_fn = candidate_fn

    def retrieve(self, query: str, top_k: int = 3, domain: str | None = None, score_threshold: float = SCORE_THRESHOLD) -> dict[str, Any]:
        rewrite = rewrite_query(query)
        candidates = self._candidate_fn(rewrite["rewritten"], domain, RECALL_POOL, score_threshold * RECALL_THRESHOLD_RATIO)
        query_feats = set(_features(rewrite["rewritten"]))
        reranked: list[KnowledgeChunk] = []
        for row in candidates:
            chunk_feats = set(_features(row["doc_title"] + row["section"] + row["content"]))
            keyword_coverage = len(query_feats & chunk_feats) / max(1, len(query_feats))
            score = row["base_score"] + KEYWORD_WEIGHT * keyword_coverage
            if score >= score_threshold:
                reranked.append(KnowledgeChunk(row["chunk_id"], row["domain"], row["doc_title"], row["section"], row["content"], score, json.loads(row["metadata"] or "{}")))
        reranked.sort(key=lambda chunk: chunk.score, reverse=True)
        return {"rewrite": rewrite, "chunks": reranked[:top_k], "candidate_count": len(candidates)}


class KnowledgeStore:
    """SQLite 持久化的知识库：knowledge_chunks 存切片/向量/metadata，knowledge_meta 存来源清单。"""

    def __init__(self, db_path: str | Path, knowledge_dir: str | Path):
        self.db_path = str(db_path)
        self.knowledge_dir = Path(knowledge_dir)
        self.loader = KnowledgeLoader()
        self.product_catalog = None
        self.retriever = KnowledgeRetriever(self._recall_candidates)
        self._ensure_tables()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """显式关闭连接的上下文管理器（with conn 只管事务，不释放 Windows 文件锁）。"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_tables(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS knowledge_chunks ("
                "chunk_id TEXT PRIMARY KEY, domain TEXT NOT NULL, doc_title TEXT NOT NULL, "
                "section TEXT NOT NULL, content TEXT NOT NULL, content_hash TEXT NOT NULL, "
                "embedding TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS knowledge_meta ("
                "file_path TEXT PRIMARY KEY, mtime REAL NOT NULL, content_hash TEXT NOT NULL)"
            )
            # M17.2 迁移：旧库补 metadata 列（历史切片置空对象）
            columns = {row[1] for row in conn.execute("PRAGMA table_info(knowledge_chunks)").fetchall()}
            if "metadata" not in columns:
                conn.execute("ALTER TABLE knowledge_chunks ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
            conn.commit()

    # ---------- M17 摄入：统一 Document 入口 ----------

    def ingest_documents(self, domain: str, documents: list[Document], source_key: str, content_hash: str, mtime: float = 0.0) -> int:
        """通用摄入：Document 列表 → 切片 + 向量 + metadata 落库；同 domain 整体替换。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM knowledge_chunks WHERE domain = ?", (domain,))
            for index, document in enumerate(documents):
                chunk_id = f"{domain}:{index}:{_content_hash(document.text)[:8]}"
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_chunks(chunk_id, domain, doc_title, section, content, content_hash, embedding, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        chunk_id,
                        domain,
                        str(document.metadata.get("doc_title") or domain),
                        str(document.metadata.get("section") or ""),
                        document.text,
                        _content_hash(document.text),
                        json.dumps(embed(document.text), ensure_ascii=False),
                        json.dumps(document.metadata, ensure_ascii=False),
                    ),
                )
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_meta(file_path, mtime, content_hash) VALUES (?, ?, ?)",
                (source_key, mtime, content_hash),
            )
            conn.commit()
        return len(documents)

    def ingest_file(self, path: Path) -> int:
        """摄入单个知识文件（markdown/excel）；返回写入切片数。同名来源旧切片整体替换。"""
        documents = self.loader.load_path(path)
        raw = path.read_bytes()
        stat = path.stat()
        return self.ingest_documents(path.stem, documents, path.name, _content_hash(raw.decode("utf-8", errors="replace")), stat.st_mtime)

    def ingest_database(self, db_path: str | Path, table: str, text_field: str, metadata_fields: tuple[str, ...] = (), category: str | None = None) -> int:
        """M17.1 DatabaseLoader 摄入：政策配置类只读数据进知识管道（禁止客户/订单表）。"""
        documents = self.loader.load_database(db_path, table, text_field, metadata_fields, category)
        sql = f"SELECT {text_field}{', ' + ', '.join(metadata_fields) if metadata_fields else ''} FROM {table}"
        return self.ingest_documents(table, documents, f"database:{table}", _content_hash(sql), 0.0)

    def ingest_api(self, name: str, fetch: Callable[[], list[dict[str, Any]]] | None = None) -> int:
        """M17.1 ApiLoader 摄入：注入式 fetch 回调；无回调（无网络环境）返回 0。"""
        documents = self.loader.load_api(name, fetch)
        return self.ingest_documents(name, documents, f"api:{name}", _content_hash(json.dumps([doc.as_dict() for doc in documents], ensure_ascii=False)), 0.0)

    def ensure_index(self) -> dict[str, int]:
        """按目录同步索引：新增/变更文件摄入，已删除文件清除旧切片。返回 {来源: 切片数}。"""
        files = sorted([p for p in self.knowledge_dir.iterdir() if p.suffix.lower() in {".md", ".xlsx", ".xlsm"}]) if self.knowledge_dir.exists() else []
        indexed: dict[str, int] = {}
        seen_domains: set[str] = set()
        for path in files:
            seen_domains.add(path.stem)
            current_hash = _content_hash(path.read_bytes().decode("utf-8", errors="replace"))
            with self._connect() as conn:
                row = conn.execute("SELECT content_hash FROM knowledge_meta WHERE file_path = ?", (path.name,)).fetchone()
            if row and row["content_hash"] == current_hash:
                with self._connect() as conn:
                    indexed[path.name] = conn.execute("SELECT COUNT(*) FROM knowledge_chunks WHERE domain = ?", (path.stem,)).fetchone()[0]
                continue
            indexed[path.name] = self.ingest_file(path)
        with self._connect() as conn:
            known = [row[0] for row in conn.execute("SELECT file_path FROM knowledge_meta").fetchall()]
            for name in known:
                if not name.startswith(("database:", "api:")) and Path(name).stem not in seen_domains:
                    conn.execute("DELETE FROM knowledge_chunks WHERE domain = ?", (Path(name).stem,))
                    conn.execute("DELETE FROM knowledge_meta WHERE file_path = ?", (name,))
            conn.commit()
        return indexed

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0]

    # ---------- M18 检索：粗排召回（存储通道）+ 独立 Retriever 精排 ----------

    def _recall_candidates(self, query: str, domain: str | None, pool: int, threshold: float) -> list[dict[str, Any]]:
        """粗排召回：宽阈值下按"语义 + 0.8*标题"基础分返回候选池（供精排重排）。"""
        query_vector = embed(query)
        sql = "SELECT chunk_id, domain, doc_title, section, content, embedding, metadata FROM knowledge_chunks"
        params: tuple[Any, ...] = ()
        if domain:
            sql += " WHERE domain = ?"
            params = (domain,)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        candidates: list[dict[str, Any]] = []
        for row in rows:
            body_score = cosine_similarity(query_vector, json.loads(row["embedding"]))
            heading_score = cosine_similarity(query_vector, embed(row["doc_title"] + row["section"]))
            base_score = body_score + 0.8 * heading_score
            if base_score >= threshold:
                candidates.append({"chunk_id": row["chunk_id"], "domain": row["domain"], "doc_title": row["doc_title"], "section": row["section"], "content": row["content"], "metadata": row["metadata"], "base_score": base_score})
        candidates.sort(key=lambda item: item["base_score"], reverse=True)
        return candidates[:pool]

    def search(self, query: str, top_k: int = 3, domain: str | None = None, score_threshold: float = SCORE_THRESHOLD) -> list[KnowledgeChunk]:
        return self.retriever.retrieve(query, top_k=top_k, domain=domain, score_threshold=score_threshold)["chunks"]

    def search_dicts(self, query: str, top_k: int = 3, domain: str | None = None) -> list[dict[str, Any]]:
        if self.product_catalog is not None and domain in (None, "product_catalog"):
            products = self.product_catalog.search(query, top_k)
            if products is not None:
                return products
        return [chunk.as_dict() for chunk in self.search(query, top_k=top_k, domain=domain)]

    def attach_product_catalog(self, source: Path) -> dict[str, Any]:
        from app.product_knowledge import ProductKnowledge

        catalog = ProductKnowledge(self.db_path)
        summary = catalog.ingest(source)
        self.product_catalog = catalog
        return summary


_DEFAULT_STORE: KnowledgeStore | None = None


def get_default_store() -> KnowledgeStore:
    """进程级默认知识库（仓库 knowledge/ + 应用 SQLite），首次调用时建索引。"""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        root = Path(__file__).resolve().parents[1]
        _DEFAULT_STORE = KnowledgeStore(root / "data/beauty_cs_agent.sqlite3", root / "knowledge")
        _DEFAULT_STORE.ensure_index()
        source = root / "data/raw/产品功能详情.jsonl"
        if source.exists():
            _DEFAULT_STORE.attach_product_catalog(source)
    return _DEFAULT_STORE
