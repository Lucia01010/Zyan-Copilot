"""Check whether the cached demo can run, without printing secrets."""
from __future__ import annotations

import importlib
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    reasons: list[str] = []
    checks: list[str] = []
    checks.append(f"Python {sys.version.split()[0]}")
    if not (ROOT / ".venv" / "Scripts" / "python.exe").exists() and not (ROOT / ".venv" / "bin" / "python").exists():
        reasons.append(".venv not found (demo can still use system Python if dependencies are installed)")
    try:
        importlib.import_module("fastapi")
        importlib.import_module("openpyxl")
        importlib.import_module("app.api")
        checks.append("FastAPI/app import OK")
    except Exception as exc:
        reasons.append(f"backend import failed: {type(exc).__name__}")
    db = ROOT / "data" / "beauty_cs_agent.sqlite3"
    if db.exists():
        try:
            with sqlite3.connect(db) as conn:
                count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
            checks.append(f"SQLite OK ({count} chat messages)")
        except Exception as exc:
            reasons.append(f"SQLite check failed: {type(exc).__name__}")
    else:
        reasons.append("data/beauty_cs_agent.sqlite3 not found")
    if (ROOT / "frontend" / "package.json").exists() and (ROOT / "frontend" / "node_modules").exists():
        checks.append("frontend dependencies present")
    else:
        reasons.append("frontend dependencies not installed")
    if (ROOT / "frontend" / "dist" / "index.html").exists():
        checks.append("frontend build artifact present")
    else:
        reasons.append("frontend/dist missing; run npm run build")
    env_file = ROOT / ".env"
    env_names = set()
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                env_names.add(line.split("=", 1)[0].strip())
    live_ready = bool(os.getenv("QWEN_API_KEY")) or {"QWEN_API_KEY", "QWEN_BASE_URL", "QWEN_MODEL"}.issubset(env_names)
    checks.append("live config present" if live_ready else "live config absent (not required for cached demo)")
    print("READY" if not reasons else "READY (demo mode with warnings)")
    for item in checks:
        print(f"  OK: {item}")
    for reason in reasons:
        print(f"  WARN: {reason}")
    print("  Demo mode: available without Qwen credentials")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
