import unittest
from unittest.mock import Mock, patch

from app.services import chatbot_product_service as service


class ProductLanguageTests(unittest.TestCase):
    def answer(self, context, language, match=None):
        db = Mock()
        products = []

        with (
            patch.object(
                service, "build_chat_context",
                return_value=context,
            ),
            patch.object(
                service, "consultation_covers_analysis",
                return_value=False,
            ),
            patch.object(
                service, "build_product_match",
                return_value=match,
            ),
        ):
            reply, action = service.product_reply(
                db,
                Mock(),
                1,
                language=language,
                products=products,
            )

        # These branches must never query or recommend products.
        db.execute.assert_not_called()
        self.assertEqual(products, [])
        return reply, action

    def test_missing_pet_translates_and_preserves_navigation(self):
        expected = {
            "en": "Start a pet-linked chat",
            "ms": "Pilih haiwan peliharaan",
            "zh": "请选择聊天关联的宠物",
        }

        for language, phrase in expected.items():
            with self.subTest(language=language):
                reply, action = self.answer({}, language)
                self.assertIn(phrase, reply)
                self.assertEqual(action, "OPEN_SHOP")

    def test_severe_assessment_still_blocks_products(self):
        context = {
            "pet": {"species": "dog"},
            "latest_analysis": {
                "analysis_id": 7,
                "estimated_severity": "severe",
            },
        }
        expected = {
            "en": "not a confirmed diagnosis",
            "ms": "bukan diagnosis yang disahkan",
            "zh": "并非确诊结果",
        }

        for language, phrase in expected.items():
            with self.subTest(language=language):
                reply, action = self.answer(context, language)
                self.assertIn(phrase, reply)
                self.assertEqual(action, "OPEN_APPOINTMENTS")

    def test_vet_feedback_and_action_are_preserved(self):
        context = {
            "pet": {"species": "cat"},
            "latest_analysis": {"analysis_id": 7},
            "vet_reviews": [{
                "analysis_id": 7,
                "review_id": 19,
                "clinic_id": 3,
                "recommended_action": "in_clinic",
                "feedback": "Original instructions 原文",
            }],
        }

        for language in ("en", "ms", "zh"):
            with self.subTest(language=language):
                reply, action = self.answer(context, language)
                self.assertIn("Original instructions 原文", reply)
                self.assertIn("in_clinic", reply)
                self.assertIn("#19", reply)
                self.assertEqual(action, "OPEN_APPOINTMENTS")

    def test_unknown_safety_explanation_is_preserved(self):
        match = {
            "tags": set(),
            "blocked_reason": "Specific safety instruction 原文",
        }

        for language in ("en", "ms", "zh"):
            with self.subTest(language=language):
                reply, action = self.answer(
                    {"pet": {"species": "dog"}},
                    language,
                    match=match,
                )
                self.assertEqual(
                    reply, "Specific safety instruction 原文"
                )
                self.assertEqual(action, "OPEN_MEDICAL_HISTORY")


if __name__ == "__main__":
    unittest.main()