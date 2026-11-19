import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services import chatbot_medical_service as medical
from app.services.chatbot_engine_service import load_chatbot_module
from app.services.chatbot_product_followup_service import (
    explain_previous_products,
)

language = load_chatbot_module("chatbot_language")
assessment = load_chatbot_module("chatbot_assessment_text")


class ChatbotLocalizationTests(unittest.TestCase):
    def test_prescription_values_are_preserved(self):
        record = {
            "consultation_id": 7,
            "consultation_date": "2026-11-20",
            "clinic_name": "Willow Clinic",
            "veterinarian_name": "Dr Tan",
            "prescriptions": [{
                "prescription_id": 3,
                "medication_name": "Recorded medicine",
                "prescription_date": "2026-11-20",
                "dosage": "0.5 mL",
                "administration_route": "oral",
                "frequency": "twice daily",
                "duration": "5 days",
                "instructions": "Original instructions 原文",
            }],
        }

        for lang in ("en", "ms", "zh"):
            with self.subTest(language=lang):
                reply = medical.prescription_reply(
                    "Milo", record, language=lang
                )
                for value in (
                    "Willow Clinic",
                    "Dr Tan",
                    "0.5 mL",
                    "twice daily",
                    "5 days",
                    "Original instructions 原文",
                ):
                    self.assertIn(value, reply)

    def test_medical_history_receives_selected_language(self):
        user = SimpleNamespace(role="pet_owner")
        pet = SimpleNamespace(pet_id=1, pet_name="Milo")

        with (
            patch.object(medical, "get_owner_profile"),
            patch.object(medical, "get_pet", return_value=pet),
            patch.object(medical, "list_medical_history", return_value=[]),
        ):
            for lang in ("en", "ms", "zh"):
                reply = medical.medical_record_reply(
                    None, user, 1, "pet_medical_history", language=lang
                )
                self.assertEqual(
                    reply,
                    medical.translated("no_history", lang, pet="Milo"),
                )

    def test_safety_reply_is_never_replaced_by_fallback_translation(self):
        for intent in ("urgent_vet_contact", "medication_referral"):
            original = {
                "intent": intent,
                "mode": "rule",
                "reply": "Original safety guidance",
            }
            for lang in ("en", "ms", "zh"):
                self.assertEqual(
                    language.localize_faq_answer(original, lang),
                    original,
                )

    def test_prediction_translation_preserves_scores_and_exclusions(self):
        context = {
            "pet": {"name": "Milo"},
            "latest_analysis": {
                "analysis_id": 7,
                "predictions": [
                    {
                        "condition": "healthy",
                        "confidence": 0.85,
                        "positive": True,
                    },
                    {
                        "condition": "calculus",
                        "confidence": 0.99,
                        "positive": False,
                        "supported": False,
                    },
                ],
            },
            "vet_reviews": [],
        }

        for lang in ("ms", "zh"):
            reply = assessment.render_assessment_reply(
                "pet_prediction_scores", context, lang
            )
            self.assertIn("85.0%", reply)
            self.assertNotIn("99.0%", reply)

    def test_missing_segmentation_is_not_reported_as_zero(self):
        context = {
            "pet": {"name": "Milo"},
            "latest_analysis": {
                "analysis_id": 7,
                "segmentation": {
                    "gingivitis_area_percent": 12.345,
                    "calculus_area_percent": None,
                },
            },
        }

        for lang in ("ms", "zh"):
            reply = assessment.render_assessment_reply(
                "pet_segmentation_values", context, lang
            )
            self.assertIn("12.35%", reply)
            self.assertNotIn("0.00%", reply)

    def test_product_explanations_preserve_saved_values(self):
        db = Mock()
        conversation = SimpleNamespace(conversation_id=1, pet_id=3)

        db.scalar.return_value = SimpleNamespace(response_metadata={
            "intent": "product_recommendation",
            "context_reference": {"pet_id": 3},
            "products": [{
                "product_name": "Pet Brush",
                "recommendation_reason": "Recorded reason: RM 18.90.",
            }],
        })

        for lang, question in (
            ("en", "why these products?"),
            ("ms", "kenapa produk ini?"),
            ("zh", "为什么推荐这些产品？"),
        ):
            reply = explain_previous_products(
                db, conversation, question, language=lang
            )
            self.assertIsNotNone(reply)
            self.assertIn("Pet Brush", reply["reply"])
            self.assertIn("RM 18.90", reply["reply"])
            self.assertEqual(reply["recommended_action"], "NONE")


if __name__ == "__main__":
    unittest.main()