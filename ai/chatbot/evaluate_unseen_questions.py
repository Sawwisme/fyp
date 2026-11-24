
import json
from datetime import datetime
from pathlib import Path

from chatbot_engine import chatbot


TEST_CASES = [
    # Dental knowledge
    ("Could you explain what gingivitis actually is?",
     "gingivitis_information"),

    ("What exactly is hardened dental tartar?",
     "calculus_information"),

    ("What is the sticky plaque on teeth?",
     "plaque_information"),

    ("Why does my puppy have stinky breath?",
     "bad_breath"),

    # Assessment requests
    ("Can I see the outcome of my latest scan?",
     "explain_latest_analysis"),

    ("Please display my previous dental assessments",
     "dental_analysis_history"),

    ("Is my pet's estimated condition mild or severe?",
     "explain_pet_severity"),

    ("Compare my latest assessment with the previous result",
     "compare_analysis_progress"),

    ("Can I see the confidence scores from my scan?",
     "pet_prediction_scores"),

    ("What should I do about my latest assessment?",
     "pet_next_steps"),

    # Informal language and spelling
    ("I wanna book an apointment",
     "book_appointment"),

    ("Can u show my prescripton?",
     "recorded_prescriptions"),

    ("Pls explain gingivtis",
     "gingivitis_information"),

    ("How often should I brush my puppy's teeth?",
     "daily_dental_care"),

    # Safety
    ("My puppy is struggling to breathe",
     "urgent_vet_contact"),

    ("My cat has no facial swelling but has severe pain",
     "urgent_vet_contact"),

    ("My kitten has stopped drinking",
     "urgent_vet_contact"),

    ("Is ibuprofen suitable for my dog?",
     "medication_referral"),

    ("Is adult toothpaste suitable for my cat?",
     "human_toothpaste_warning"),

    # Out-of-scope and ambiguous questions
    ("Can you help me repair my computer?",
     "clarify"),

    ("What is the capital of Japan?",
     "clarify"),

    ("Recommend a gaming laptop",
     "clarify"),

    ("Can you predict tomorrow's stock market?",
     "clarify"),

    ("Tell me something",
     "clarify"),

    ("Can you help?",
     "clarify"),
]


def evaluate():
    results = []
    correct = 0

    for question, expected in TEST_CASES:
        answer = chatbot.answer(question)
        actual = answer["intent"]
        passed = actual == expected

        if passed:
            correct += 1

        results.append({
            "question": question,
            "expected_intent": expected,
            "actual_intent": actual,
            "passed": passed,
            "mode": answer["mode"],
            "similarity": answer.get("similarity"),
            "nlp_metrics": answer.get("nlp_metrics"),
        })

        print("=" * 65)
        print("Question:", question)
        print("Expected:", expected)
        print("Actual:", actual)
        print("Result:", "PASS" if passed else "FAIL")

    total = len(TEST_CASES)
    accuracy = correct / total * 100

    print("\n" + "=" * 65)
    print("UNSEEN QUESTION EVALUATION")
    print("=" * 65)
    print(f"Total questions: {total}")
    print(f"Correct: {correct}")
    print(f"Incorrect: {total - correct}")
    print(f"Intent accuracy: {accuracy:.2f}%")

    report = {
        "evaluation_type": "unseen_question_evaluation",
        "total_questions": total,
        "correct": correct,
        "incorrect": total - correct,
        "intent_accuracy": round(accuracy, 2),
        "results": results,
    }

    report_dir = (
        Path(__file__).resolve().parent
        / "evaluation_reports"
        / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )

    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / "unseen_evaluation.json"

    report_path.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    evaluate()
