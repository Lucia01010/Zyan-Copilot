import unittest

from app.error_compactor import compact_tool_error


class ErrorCompactorTests(unittest.TestCase):
    def test_unexpected_keyword_parameter_is_extracted(self):
        try:
            raise TypeError("get_order() got an unexpected keyword argument 'time_range'")
        except TypeError as exc:
            compact = compact_tool_error("get_order", exc)
        self.assertEqual(compact["error_type"], "TypeError")
        self.assertEqual(compact["offending_parameter"], "time_range")
        self.assertIn("schema", compact["suggestion"])
        self.assertIn("get_order", compact["error_summary"])
        self.assertEqual(compact["message"], "get_order() got an unexpected keyword argument 'time_range'")

    def test_missing_argument_is_extracted(self):
        try:
            raise TypeError("get_order() missing 1 required positional argument: 'order_number'")
        except TypeError as exc:
            compact = compact_tool_error("get_order", exc)
        self.assertEqual(compact["offending_parameter"], "order_number")
        self.assertIn("order_number", compact["suggestion"])

    def test_keyerror_maps_to_missing_field(self):
        try:
            raise KeyError("order_number")
        except KeyError as exc:
            compact = compact_tool_error("check_order", exc)
        self.assertEqual(compact["offending_parameter"], "order_number")
        self.assertIn("不要编造", compact["suggestion"])

    def test_json_decode_error_gets_repair_hint(self):
        import json as _json

        try:
            _json.loads("{bad json")
        except _json.JSONDecodeError as exc:
            compact = compact_tool_error("check_order", exc)
        self.assertIn("JSON", compact["suggestion"])
        self.assertNotIn("offending_parameter", compact)

    def test_generic_error_stays_compact_and_omits_empty_field(self):
        try:
            raise RuntimeError("database is locked")
        except RuntimeError as exc:
            compact = compact_tool_error("check_order", exc)
        self.assertEqual(compact["error_type"], "RuntimeError")
        self.assertEqual(compact["message"], "database is locked")
        self.assertNotIn("offending_parameter", compact)
        self.assertLessEqual(len(compact), 4)
        self.assertIn("进一步核实", compact["suggestion"])

    def test_long_message_is_truncated_to_first_line(self):
        try:
            raise RuntimeError("boom\n" + "x" * 500)
        except RuntimeError as exc:
            compact = compact_tool_error("check_order", exc)
        self.assertEqual(compact["message"], "boom")
        self.assertLessEqual(len(compact["message"]), 200)


if __name__ == "__main__":
    unittest.main()
