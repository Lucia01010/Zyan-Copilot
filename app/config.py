"""配置外置化：无第三方依赖的微型 .env 加载器。

启动时把仓库根目录 .env 的 KEY=VALUE 注入进程环境：
- 已存在的真实环境变量优先（如启动脚本注入的 AGENT_PROVIDER=mock 不会被覆盖）；
- 密钥只存 .env（不入库），.env.example 仅保留占位符。
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def parse_env(text: str) -> dict[str, str]:
    """解析 KEY=VALUE 文本：忽略空行与 # 注释行，剥离首尾空白与成对引号。"""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_env(path: str | Path | None = None) -> int:
    """把 .env 中进程环境尚不存在的键注入 os.environ；返回实际注入的键数量。"""
    env_path = Path(path) if path else DEFAULT_ENV_PATH
    if not env_path.is_file():
        return 0
    applied = 0
    for key, value in parse_env(env_path.read_text(encoding="utf-8")).items():
        if key not in os.environ:
            os.environ[key] = value
            applied += 1
    return applied
