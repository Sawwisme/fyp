
import unittest

from chatbot_engine import chatbot
from chatbot_safety import multilingual_safety_reply


class TestChatbotSafety(unittest.TestCase):

    def test_emergency_messages(self):
        cases = [
            "My dog cannot breathe",
            "My cat has heavy bleeding",
            "My dog has severe pain",
            "My cat is unconscious",
            "My dog is not breathing",
            "My dog has no facial swelling but cannot breathe",
            "My cat has no severe pain but has heavy bleeding",
        ]

        for message in cases:
            with self.subTest(message=message):
                safety = multilingual_safety_reply(message)

                self.assertIsNotNone(safety)
                self.assertEqual(
                    safety["urgency_level"],
                    "emergency",
                )

                answer = chatbot.answer(message)

                self.assertEqual(
                    answer["intent"],
                    "urgent_vet_contact",
                )

    def test_negated_symptoms(self):
        cases = [
            "My dog has no facial swelling",
            "My cat has no severe pain",
            "My dog has no heavy bleeding",
            "My cat is not unconscious",
        ]

        for message in cases:
            with self.subTest(message=message):
                self.assertIsNone(
                    multilingual_safety_reply(message)
                )

                answer = chatbot.answer(message)

                self.assertNotEqual(
                    answer["intent"],
                    "urgent_vet_contact",
                )

    def test_prompt_assessment(self):
        cases = [
            "My dog is not eating",
            "My cat cannot eat",
            "My dog has a broken tooth",
            "My cat is not drinking",
        ]

        for message in cases:
            with self.subTest(message=message):
                answer = multilingual_safety_reply(message)

                self.assertIsNotNone(answer)
                self.assertEqual(
                    answer["urgency_level"],
                    "prompt",
                )

                self.assertEqual(
                    chatbot.answer(message)["intent"],
                    "urgent_vet_contact",
                )

    def test_multilingual_emergencies(self):
        cases = [
            ("我的狗无法呼吸", "zh"),
            ("我的猫呼吸困难", "zh"),
            ("Kucing saya susah bernafas", "ms"),
            ("Anjing saya tidak boleh bernafas", "ms"),
        ]

        for message, language in cases:
            with self.subTest(message=message):
                answer = multilingual_safety_reply(message)

                self.assertIsNotNone(answer)
                self.assertEqual(
                    answer["urgency_level"],
                    "emergency",
                )
                self.assertEqual(
                    answer["language"],
                    language,
                )

    def test_medication_safety(self):
        answer = chatbot.answer(
            "Can I give my cat paracetamol?"
        )

        self.assertEqual(
            answer["intent"],
            "medication_referral",
        )

    def test_toothpaste_safety(self):
        answer = chatbot.answer(
            "Can I use human toothpaste?"
        )

        self.assertEqual(
            answer["intent"],
            "human_toothpaste_warning",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
