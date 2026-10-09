import os
import tempfile
import unittest
from pathlib import Path

from app.config import load_env, parse_env


class ParseEnvTests(unittest.TestCase):
    def test_parses_key_value_strips_quotes_comments_and_blank_lines(self):
        text = "\n".join([
            "# 注释行",
            "",
            "QWEN_MODEL=qwen3.7-plus",
            "QWEN_API_KEY='sk-secret'",
            'QWEN_BASE_URL="https://example.com/v1"',
            "  SPACED =  value  ",
            "NO_EQUALS_LINE",
        ])
        self.assertEqual(parse_env(text), {"QWEN_MODEL": "qwen3.7-plus", "QWEN_API_KEY": "sk-secret", "QWEN_BASE_URL": "https://example.com/v1", "SPACED": "value"})


class LoadEnvTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.env_file = Path(self._tmp.name) / ".env"

    def tearDown(self):
        for key in ("CFG_LOADER_A", "CFG_LOADER_B"):
            os.environ.pop(key, None)
        self._tmp.cleanup()

    def test_applies_missing_keys_and_keeps_existing_env(self):
        os.environ["CFG_LOADER_B"] = "real"
        self.env_file.write_text("CFG_LOADER_A=from_file\nCFG_LOADER_B=from_file\n", encoding="utf-8")
        applied = load_env(self.env_file)
        self.assertEqual(applied, 1)
        self.assertEqual(os.environ["CFG_LOADER_A"], "from_file")
        self.assertEqual(os.environ["CFG_LOADER_B"], "real")  # 真实环境变量优先，不被覆盖

    def test_missing_file_is_noop(self):
        self.assertEqual(load_env(Path(self._tmp.name) / "nope.env"), 0)


class EnvExampleHygieneTests(unittest.TestCase):
    """工作区规则：.env.example 只允许占位符，不得混入真实密钥。"""

    def test_example_uses_placeholder_and_covers_all_config_keys(self):
        root = Path(__file__).resolve().parents[1]
        values = parse_env((root / ".env.example").read_text(encoding="utf-8"))
        self.assertEqual(values["QWEN_API_KEY"], "sk-your-key-here")
        for key in ("BEAUTY_DB_PATH", "AGENT_PROVIDER", "QWEN_MOCK", "QWEN_BASE_URL", "QWEN_MODEL", "QWEN_TIMEOUT", "QWEN_TEMPERATURE", "QWEN_FREE_ONLY", "QWEN_MAX_TOKENS", "QWEN_MAX_TOOL_ROUNDS", "QWEN_ENABLE_THINKING", "QWEN_DEBUG_DIR", "QWEN_EVAL_TOKEN_BUDGET", "VITE_API_URL"):
            self.assertIn(key, values, f".env.example 缺少键: {key}")


if __name__ == "__main__":
    unittest.main()
