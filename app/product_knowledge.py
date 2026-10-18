"""Source-backed product graph, isolated from business records and generic RAG."""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from pathlib import Path


def clean(value) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))).strip()


def labels(value) -> list[str]:
    return [re.sub(r"^\d+\s*", "", x).strip() for x in re.split(r"[,，、]", clean(value)) if x.strip()]


class ProductKnowledge:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS product_knowledge (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS product_relations (
                    product_id TEXT, relation TEXT, value TEXT, source_field TEXT,
                    PRIMARY KEY(product_id, relation, value, source_field));
                CREATE TABLE IF NOT EXISTS product_source (
                    source TEXT PRIMARY KEY, sha256 TEXT NOT NULL, count INTEGER NOT NULL);
            """)

    def ingest(self, path: Path) -> dict:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            previous = conn.execute("SELECT sha256,count FROM product_source WHERE source=?", (path.name,)).fetchone()
            if previous and previous[0] == digest:
                return {"products": previous[1], "changed": False, "sha256": digest}
            products, edges, seen = [], [], set()
            for line, text in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
                if not text.strip():
                    continue
                row = json.loads(text)
                info, efficacy = row.get("product_info") or {}, row.get("efficacy") or {}
                claim = efficacy.get("gxxc") or {}
                pid = str(row.get("id") or "")
                if not pid or pid in seen or not info.get("prodName"):
                    raise ValueError(f"Invalid or duplicate product at line {line}")
                seen.add(pid)
                relations = [("efficacy", x, "efficacy.gxxc.cpgx") for x in labels(claim.get("cpgx"))]
                relations += [("body_part", x, "efficacy.gxxc.zybw") for x in labels(claim.get("zybw"))]
                relations += [("population", x, "efficacy.gxxc.syrq") for x in labels(claim.get("syrq"))]
                for item in efficacy.get("gxxccps") or []:
                    name = clean(item.get("gxmc"))
                    if name:
                        relations.append(("claim", name, "efficacy.gxxccps.gxmc"))
                product = {"id": pid, "name": clean(info.get("prodName")), "brand": clean(info.get("entName")),
                           "usage": clean(info.get("syff")), "warnings": clean(info.get("aqjsyy")) + " " + clean(info.get("zysx")),
                           "ingredients": clean(info.get("component")), "storage": clean(info.get("zctj")),
                           "shelf_life": clean(info.get("syqx")), "offdate": clean(info.get("offdate")),
                           "record_no": clean(info.get("recordNo")), "claims": [x[1] for x in relations],
                           "source": path.name, "source_line": line, "sha256": digest,
                           "scraped_at": row.get("scraped_at"), "relations": relations}
                products.append((pid, json.dumps(product, ensure_ascii=False)))
                edges.extend((pid, *edge) for edge in relations)
            # Validate the entire file before atomically replacing this dedicated catalog.
            conn.execute("DELETE FROM product_knowledge")
            conn.execute("DELETE FROM product_relations")
            conn.execute("DELETE FROM product_source")
            conn.executemany("INSERT INTO product_knowledge VALUES (?,?)", products)
            conn.executemany("INSERT OR IGNORE INTO product_relations VALUES (?,?,?,?)", edges)
            conn.execute("INSERT INTO product_source VALUES (?,?,?)", (path.name, digest, len(products)))
        return {"products": len(products), "relations": len(set(edges)), "changed": True, "sha256": digest}

    def search(self, query: str, top_k: int = 3) -> list[dict] | None:
        with sqlite3.connect(self.db_path) as conn:
            products = [json.loads(r[0]) for r in conn.execute("SELECT payload FROM product_knowledge")]
        exact = [p for p in products if p["name"] in query or p["record_no"] and p["record_no"] in query]
        categories = [x for x in ("面膜", "眼膜", "精华", "面霜", "眼霜", "乳液", "洁面", "洗发", "护发", "口红", "防晒") if x in query]
        brands = {p["brand"] for p in products if p["brand"] and p["brand"] in query}
        if "品牌" in query and not brands:
            return [{"chunk_id": "product:insufficient", "domain": "product_catalog", "doc_title": "选品信息待确认",
                     "section": "资料边界", "score": 0, "metadata": {},
                     "text": "现有资料中未找到该品牌的产品依据。请补充产品完整备案名或可核对的品牌信息。"}]
        needs = [x for x in ("保湿", "修护", "抗皱", "紧致", "控油", "舒缓", "清洁", "美白", "防晒") if x in query]
        skin = [x for x in ("敏感", "干性", "油性", "混合性") if x in query]
        recommendation = any(x in query for x in ("推荐", "选品", "买什么", "选什么", "适合", "适用"))
        # Keep broad how-to questions on the curated policy RAG; use the catalog
        # for a named product or an explicit selection/recommendation request.
        if not (exact or brands or recommendation):
            return None  # Generic policy RAG remains available.
        ranked = []
        for p in exact or products:
            if not exact:
                if p["offdate"] or not p["usage"]:
                    continue
                if brands and p["brand"] not in brands:
                    continue
                if categories and not any(c in p["name"] for c in categories):
                    continue
                claims = " ".join(p["claims"])
                if needs and not all(n in claims for n in needs):
                    continue
                if skin and not all(s in claims for s in skin):
                    continue
                if not (brands or categories or needs or skin):
                    continue
            score = 100 if exact else sum(n in " ".join(p["claims"]) for n in needs) + 1
            ranked.append((score, p))
        ranked.sort(key=lambda x: (-x[0], x[1]["id"]))
        matches = []
        for score, p in ranked[:top_k]:
            fields = [("备案功效/适用信息", "、".join(p["claims"]))]
            if "成分" in query:
                fields.append(("成分", p["ingredients"]))
            elif any(x in query for x in ("保存", "保质期")):
                fields += [("保存", p["storage"]), ("保质期", p["shelf_life"])]
            else:
                fields.append(("使用方法", p["usage"]))
            fields.append(("注意事项", p["warnings"].strip()))
            body = p["name"] + "。" + "；".join(f"{k}：{v or '原始资料未提供'}" for k, v in fields)
            body += "。肤质适配仅以明确宣称为依据；备案信息不代表当前在售，购买前需核对在售版本。"
            if p["offdate"]:
                body += "该记录存在注销日期：" + p["offdate"] + "，不作为选品推荐。"
            matches.append({"chunk_id": "product:" + p["id"], "domain": "product_catalog", "doc_title": p["name"],
                            "section": "产品备案资料", "text": body, "score": score,
                            "metadata": {k: p[k] for k in ("id", "record_no", "source", "source_line", "sha256", "scraped_at", "relations")}})
        if not matches:
            return [{"chunk_id": "product:insufficient", "domain": "product_catalog", "doc_title": "选品信息待确认",
                     "section": "资料边界", "score": 0, "metadata": {},
                     "text": "现有资料中未找到满足这些条件的产品依据。请补充产品完整备案名或品牌、品类、肤质及主要需求；不能据此保证肤质适配或推荐替代产品。"}]
        return matches
