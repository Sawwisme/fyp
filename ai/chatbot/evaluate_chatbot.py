import json
from datetime import datetime, timezone
from pathlib import Path

from chatbot_engine import chatbot
from chatbot_knowledge import KNOWLEDGE


MANUAL_CASES = [
    ("hello", "greeting"),
    ("please explain dental plaque", "plaque_information"),
    ("explain dental tartar", "calculus_information"),
    ("what does gingivitis mean", "gingivitis_information"),
    ("is the AI result a confirmed diagnosis", "ai_interpretation"),
    ("what does the heatmap represent", "explain_gradcam"),
    ("explain the segmentation mask", "explain_segmentation"),
    ("what does classification confidence tell me", "explain_confidence"),
    ("please show my latest dental analysis", "explain_latest_analysis"),
    ("show the estimated severity for my pet", "explain_pet_severity"),
    ("show my previous dental scan results", "dental_analysis_history"),
    ("compare my latest scan with the earlier one", "compare_analysis_progress"),
    ("what should I do after my dental scan", "pet_next_steps"),
    ("tell me when my next appointment is", "upcoming_appointment"),
    ("show the followup instructions from my vet", "my_followup_care"),
    ("show the prescriptions recorded at my last visit", "recorded_prescriptions"),
    ("show my past completed consultations", "pet_medical_history"),
    ("show my pet saved segmentation measurements", "pet_segmentation_values"),
    ("show available pet dental products", "product_recommendation"),
    ("how frequently do I need to brush teeth", "daily_dental_care"),
    ("how can I brush my cat teeth", "brushing_technique"),
    ("my cat breath smells bad", "bad_breath"),
    ("what warning signs indicate dental problems", "dental_warning_signs"),
    ("my cat cannot breathe", "urgent_vet_contact"),
    ("my dog has severe pain", "urgent_vet_contact"),
    ("calculate a medication dosage", "medication_referral"),
    ("can I use human toothpaste", "human_toothpaste_warning"),
    ("tell me a joke", "clarify"),
    ("my dog likes tennis", "clarify"),
    ("what is the weather tomorrow", "clarify"),
]


def evaluate(cases):
    results = []

    for question, expected in cases:
        try:
            answer = chatbot.answer(question)

            actual = answer["intent"]
            mode = answer["mode"]
            similarity = answer.get("similarity")
            error = None
        except Exception as exception:
            actual = "engine_error"
            mode = "error"
            similarity = None
            error = type(exception).__name__

        results.append({
            "question": question,
            "expected_intent": expected,
            "actual_intent": actual,
            "matched": actual == expected,
            "mode": mode,
            "similarity": similarity,
            "error": error,
        })

    correct = sum(item["matched"] for item in results)

    labels = sorted({
        label
        for item in results
        for label in (
            item["expected_intent"],
            item["actual_intent"],
        )
    })

    per_intent = {}

    for label in labels:
        true_positive = sum(
            item["expected_intent"] == label
            and item["actual_intent"] == label
            for item in results
        )

        false_positive = sum(
            item["expected_intent"] != label
            and item["actual_intent"] == label
            for item in results
        )

        false_negative = sum(
            item["expected_intent"] == label
            and item["actual_intent"] != label
            for item in results
        )

        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )

        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        per_intent[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(
                item["expected_intent"] == label
                for item in results
            ),
        }

    return {
        "total": len(results),
        "correct": correct,
        "match_rate_percent": round(
            correct / len(results) * 100,
            2,
        ) if results else 0.0,
        "per_intent": per_intent,
        "failures": [
            item for item in results
            if not item["matched"]
        ],
        "results": results,
    }


def main():
    knowledge_cases = [
        (question, entry["intent"])
        for entry in KNOWLEDGE
        for question in entry["questions"]
    ]

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "Intent routing only. Does not evaluate medical "
            "correctness, database access or mobile navigation."
        ),
        "knowledge_example_regression": evaluate(knowledge_cases),
        "additional_manual_cases": evaluate(MANUAL_CASES),
    }

    stamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    output = (
        Path(__file__).resolve().parent
        / "evaluation_reports"
        / stamp
    )

    output.mkdir(parents=True, exist_ok=False)

    report_path = output / "intent_evaluation.json"

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    for key, title in (
        ("knowledge_example_regression", "Knowledge examples"),
        ("additional_manual_cases", "Additional manual cases"),
    ):
        section = report[key]

        print(
            f"{title}: "
            f"{section['correct']}/{section['total']} matched "
            f"({section['match_rate_percent']}%)"
        )

        for failure in section["failures"]:
            print(
                f"  MISMATCH: {failure['question']!r}\n"
                f"    Expected: {failure['expected_intent']}\n"
                f"    Actual:   {failure['actual_intent']}"
            )

    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()