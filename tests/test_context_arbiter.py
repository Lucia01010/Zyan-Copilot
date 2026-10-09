import unittest

from app.context_arbiter import arbitrate_messages, arbitrate_orders


def _messages(texts: list[str]) -> list[dict]:
    return [{"message_id": f"m{i}", "message_text": text} for i, text in enumerate(texts)]


class ArbitrateMessagesTests(unittest.TestCase):
    def test_short_session_passes_through_unchanged(self):
        messages = _messages(["你好", "我要退款"])
        result, stats = arbitrate_messages(messages, max_messages=6)
        self.assertEqual(result, messages)
        self.assertEqual(stats, {"total": 2, "kept": 2, "compressed": 0, "dropped": 0})

    def test_latest_message_is_always_kept(self):
        messages = _messages([f"常规消息{i}" for i in range(20)] + ["好的"])
        result, _ = arbitrate_messages(messages, max_messages=6)
        self.assertEqual(result[-1]["message_id"], f"m{len(messages) - 1}")
        self.assertEqual(result[-1]["message_text"], "好的")  # 最新消息即使像寒暄也完整保留

    def test_core_intent_survives_fifo_eviction(self):
        early = "我在你们家买了精华液用了之后过敏烂脸，要求赔偿"
        texts = ["你好"] + [f"第{i}轮普通沟通内容" for i in range(15)] + ["请帮我查一下", "好的我看看"]
        messages = _messages([early] + texts)
        result, stats = arbitrate_messages(messages, max_messages=6)
        kept_texts = [item["message_text"] for item in result]
        self.assertTrue(any("过敏烂脸" in text for text in kept_texts), f"核心诉求被挤出: {kept_texts}")
        self.assertLessEqual(len(result), 12)
        self.assertEqual(stats["kept"] + stats["compressed"] + stats["dropped"], stats["total"])

    def test_pleasantry_dropped_before_background(self):
        texts = ["好的"] + [f"第{i}轮普通沟通内容，无关键信息" for i in range(10)] + ["我要退款，请尽快处理"]
        result, stats = arbitrate_messages(_messages(texts), max_messages=4)
        kept_texts = [item["message_text"] for item in result]
        self.assertNotIn("好的", kept_texts)
        self.assertGreaterEqual(stats["dropped"], 1)

    def test_entity_overflow_is_compressed_not_dropped(self):
        texts = [
            f"您好，订单号 ORD{i:0>10} 金额¥{(i + 1) * 10}.00 的精华液还没收到，物流一直没更新，麻烦帮我催一下，之前买过很多次了，这次真的等太久了，希望尽快处理，谢谢"
            for i in range(15)
        ]
        result, stats = arbitrate_messages(_messages(texts), max_messages=4, max_entries=8)
        truncated = [item for item in result if item.get("text_truncated")]
        self.assertGreater(len(truncated), 0)
        for item in truncated:
            self.assertIn("关键实体", item["message_text"])
            self.assertIn("ORD", item["message_text"])
            self.assertLessEqual(len(item["message_text"]), 130)
        self.assertEqual(stats["compressed"], len(truncated))

    def test_index_order_preserved(self):
        early = "我要退货退款，订单号 ORD12345678"
        texts = [early] + [f"普通轮次{i}" for i in range(10)] + ["好的"]
        result, _ = arbitrate_messages(_messages(texts), max_messages=5)
        indices = [int(item["message_id"][1:]) for item in result]
        self.assertEqual(indices, sorted(indices))


class ArbitrateOrdersTests(unittest.TestCase):
    def test_short_list_passes_through(self):
        orders = [{"order_number": "A1"}, {"order_number": "A2"}]
        result, stats = arbitrate_orders(orders, None, [], max_orders=3)
        self.assertEqual(result, orders)
        self.assertEqual(stats, {"total": 2, "kept": 2})

    def test_preferred_and_mentioned_orders_rank_first(self):
        orders = [{"order_number": "LOW"}, {"order_number": "MENTIONED"}, {"order_number": "PREFERRED"}, {"order_number": "LOW2"}]
        messages = [{"message_text": "订单号 MENTIONED 还没收到"}]
        result, stats = arbitrate_orders(orders, "PREFERRED", messages, max_orders=2)
        self.assertEqual([item["order_number"] for item in result], ["PREFERRED", "MENTIONED"])
        self.assertEqual(stats, {"total": 4, "kept": 2})


if __name__ == "__main__":
    unittest.main()
