"""Reset only demo tracking state; raw competition data is never modified."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def main() -> int:
    db_path = Path(os.getenv("BEAUTY_DB_PATH", "data/beauty_cs_agent.sqlite3"))
    if not db_path.exists():
        print(f"NOT READY: database not found: {db_path}")
        return 2
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS risk_tracking (risk_id TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        cleared = conn.execute("SELECT COUNT(*) FROM risk_tracking").fetchone()[0]
        conn.execute("DELETE FROM risk_tracking")
        conn.commit()
    print(f"Demo reset complete: cleared {cleared} risk tracking overrides; source data unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
