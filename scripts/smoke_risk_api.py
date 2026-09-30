"""Validate the running M6 risk API using only the Python standard library."""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request


def request(base: str, path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    risks = request(base, "/api/risks")
    if not risks.get("items"):
        raise SystemExit("no risk items returned")
    risk = risks["items"][0]
    risk_id = urllib.parse.quote(risk["id"], safe="")
    updated = request(base, f"/api/risks/{risk_id}", "PATCH", {"status": "processing", "note": "smoke-test"})
    assert updated["status"] == "processing"
    restored = request(base, f"/api/risks/{risk_id}", "PATCH", {"status": "open", "note": ""})
    assert restored["status"] == "open"
    print(json.dumps({"risk_total": risks["total"], "detail_fields": sorted(risk.keys()), "status_persistence": "ok"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
