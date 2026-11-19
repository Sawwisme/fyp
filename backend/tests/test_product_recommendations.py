"""Offline rules and real product-query regressions; no MySQL connection."""
import copy
import json
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from app.database import Base
from app.models import Clinic, Product, ProductCategory
from app.services import chatbot_product_service as service
from app.services.product_recommendation_rules import build_product_match


def context(diagnosis="Routine dental assessment", instructions="", consultation=True):
    return {
        "pet": {"name": "Milo", "species": "cat", "date_of_birth": "2020-01-01"},
        "latest_analysis": None,
        "vet_reviews": [],
        "latest_consultation": {
            "consultation_id": 7, "clinic_id": 1,
            "diagnosis": diagnosis, "home_care_instructions": instructions,
        } if consultation else None,
    }


class ProductRulesTests(unittest.TestCase):
    def test_routine_labels_support_generic_and_explicit_requests(self):
        for label in ["Routine dental assessment", "routine dental check", "Routine dental care",
                      " ROUTINE   DENTAL ASSESSMENT. ", "Preventive dental care"]:
            for request in ["recommend products", "recommend products for routine brushing"]:
                with self.subTest(label=label, request=request):
                    result = build_product_match(context(label), request)
                    self.assertEqual(result["tags"], {"routine_oral_hygiene"})
                    self.assertEqual(result["source"], "Consultation #7")

    def test_disease_mapping_retains_priority(self):
        for label in ["Plaque", "Gingivitis", "Calculus", "Tartar"]:
            self.assertEqual(build_product_match(context(label), "routine brushing")["tags"], {"plaque_control"})

    def test_explicit_instructions_retain_priority(self):
        self.assertEqual(build_product_match(context(instructions="plaque control"), "routine brushing")["tags"], {"plaque_control"})

    def test_restrictions_and_complex_findings_still_block(self):
        for instructions in ["Avoid brushing", "Possible abscess", "Severe pain", "After extraction"]:
            result = build_product_match(context(instructions=instructions), "routine brushing")
            self.assertTrue(result["blocked_reason"])
            self.assertFalse(result["tags"])

    def test_missing_consultation_needs_explicit_purpose(self):
        self.assertFalse(build_product_match(context(consultation=False), "recommend products")["tags"])
        self.assertEqual(build_product_match(context(consultation=False), "routine brushing")["tags"], {"routine_oral_hygiene"})

    def test_unknown_or_empty_findings_do_not_imply_routine_care(self):
        for diagnosis in ["", "Dental examination", "Unclassified lesion"]:
            self.assertFalse(build_product_match(context(diagnosis), "routine brushing")["tags"])

    def test_unrecognized_instructions_are_not_overridden(self):
        self.assertFalse(build_product_match(context(instructions="Liquid diet"), "routine brushing")["tags"])

    def test_input_records_are_unchanged(self):
        data = context()
        before = copy.deepcopy(data)
        build_product_match(data, "recommend products")
        self.assertEqual(data, before)


class ProductQueryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def functions(connection, record):
            connection.create_function("json_quote", 1, json.dumps)
            connection.create_function("json_contains", 2, lambda container, value: int(json.loads(value) in (json.loads(container) if container else [])))
        Base.metadata.create_all(self.engine, tables=[Clinic.__table__, ProductCategory.__table__, Product.__table__])
        self.db = Session(self.engine)
        self.db.add_all([
            Clinic(clinic_id=1, clinic_code="C1", clinic_name="Clinic One", status="active", shop_pickup_enabled=True),
            Clinic(clinic_id=2, clinic_code="C2", clinic_name="Closed", status="inactive"),
            Clinic(clinic_id=3, clinic_code="C3", clinic_name="No shop", status="active", shop_pickup_enabled=False, shop_delivery_enabled=False),
            ProductCategory(category_id=1, clinic_id=1, category_name="Toothbrushes"),
        ])
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def product(self, name, **changes):
        values = dict(clinic_id=1, category_id=1, product_name=name, price=20,
                      stock_quantity=10, status="active", target_species="cat",
                      minimum_age_months=12, recommendation_enabled=1,
                      recommendation_tags=["routine_oral_hygiene"])
        values.update(changes)
        self.db.add(Product(**values))
        self.db.flush()

    def recommend(self, data=None):
        products = []
        with patch.object(service, "build_chat_context", return_value=data or context()):
            service.product_reply(self.db, None, 1, products=products, request_text="recommend products under RM 30")
        return products

    def test_real_query_preserves_all_eligibility_checks(self):
        self.product("Eligible brush")
        invalid = [
            {"recommendation_tags": []}, {"recommendation_tags": ["plaque_control"]},
            {"recommendation_enabled": 0}, {"stock_quantity": 0}, {"status": "inactive"},
            {"target_species": "dog"}, {"minimum_age_months": 600},
            {"minimum_age_months": None}, {"price": 0}, {"price": 50},
            {"clinic_id": 2}, {"clinic_id": 3},
        ]
        for i, changes in enumerate(invalid):
            self.product(f"Dental toothbrush {i}", **changes)
        self.assertEqual([p["product_name"] for p in self.recommend()], ["Eligible brush"])

    def test_dental_name_without_care_tag_does_not_match(self):
        self.product("Dental plaque toothbrush toothpaste", recommendation_tags=[])
        self.assertEqual(self.recommend(), [])

    def test_unreviewed_severe_assessment_still_blocks(self):
        self.product("Eligible brush")
        data = context()
        data["latest_analysis"] = {"analysis_id": 9, "estimated_severity": "severe"}
        self.assertEqual(self.recommend(data), [])


if __name__ == "__main__":
    unittest.main()
