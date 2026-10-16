import unittest

from app.action_registry import CAPABILITY_RESPONSE, classify_copilot_intent


class CopilotChatRoutingTests(unittest.TestCase):
    def test_capability_question_is_not_business_query(self):
        self.assertEqual(classify_copilot_intent("你能做什么"), "capability_question")
        self.assertEqual(classify_copilot_intent("介绍一下自己"), "capability_question")
        self.assertIn("我是知妍·伴答", CAPABILITY_RESPONSE)

    def test_business_and_risk_queries_route_to_tools(self):
        self.assertEqual(classify_copilot_intent("帮我查一下物流"), "business_query")
        self.assertEqual(classify_copilot_intent("为什么这个客户风险这么高"), "risk_query")


if __name__ == "__main__":
    unittest.main()
