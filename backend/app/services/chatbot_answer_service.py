from app.services.chatbot_context_service import build_chat_context
from app.services.chatbot_engine_service import generate_reply, load_chatbot_module

_assessment_text = load_chatbot_module("chatbot_assessment_text")
from app.services.chatbot_appointment_service import (
    upcoming_appointment_reply,
)
from app.services.chatbot_followup_service import resolve_followup
from app.services.chatbot_care_service import followup_care_reply
from app.services.chatbot_product_service import product_reply
from app.services.chatbot_medical_service import medical_record_reply
from app.services.chatbot_product_followup_service import (
    resolve_product_budget,
    explain_previous_products,
)

from datetime import datetime, timezone
import re

CONTEXT_INTENTS = {
    "explain_latest_analysis",
    "explain_pet_severity",
    "dental_analysis_history",
    "compare_analysis_progress",
    "pet_next_steps",
    "pet_segmentation_values",
    "pet_prediction_scores",
}


CONDITION_NAMES = {
    "healthy": "a healthy classification",
    "plaque": "plaque",
    "gingivitis": "gingivitis",
    "calculus": "calculus",
}


def date_label(analysis):
    value = analysis.get("analysis_date")
    return value[:10] if isinstance(value, str) else "date unavailable"


def severity_label(analysis):
    value = analysis.get("estimated_severity")

    if value == "inconclusive":
        return "inconclusive — no severity assigned"

    if value == "none":
        return "no disease severity assigned"

    if value in {"mild", "moderate", "severe"}:
        return value.title()

    return "unavailable"


def latest_description(pet_name, analysis):
    prefix = (
        f"{pet_name}'s latest completed assessment "
        f"({date_label(analysis)})"
    )

    decision = analysis.get("assessment_decision") or {}
    status = decision.get("status")
    reason = decision.get("reason") or ""

    if status == "inconclusive":
        return (
            f"{prefix} is inconclusive. {reason} "
            "The model flags are retained for review, "
            "but no overall severity is assigned. "
            "This does not establish either disease or health."
        )

    if status == "unavailable":
        return (
            f"{prefix} does not have a usable interpretation. "
            f"{reason}"
        )

    if status == "healthy_pattern":
        return (
            f"{prefix} has no disease flags above their thresholds. "
            "This image-screening result does not rule out "
            "dental problems."
        )

    conditions = [
        condition
        for condition in analysis.get("detected_conditions", [])
        if condition in {"plaque", "gingivitis", "calculus"}
    ]

    flags = ", ".join(conditions) or "no disease flags"

    return (
        f"{prefix} recorded model flags for: {flags}. "
        f"Experimental severity: {severity_label(analysis)}. "
        "These are screening outputs, not confirmed diagnoses."
    )

def vet_feedback(context, analysis_id):
    # Only feedback for this particular analysis.
    matches = [
        review
        for review in context.get("vet_reviews", [])
        if review["analysis_id"] == analysis_id
    ]

    if not matches:
        return ""

    # Keep different clinics' reviews separate.
    sections = []

    for review in matches:
        reviewed = review.get("reviewed_severity")
        action = review.get("recommended_action")

        sections.append(
            f"Recorded vet review #{review['review_id']} "
            f"(clinic #{review['clinic_id']}): "
            f"{review.get('feedback') or 'No feedback recorded.'} "
            f"Vet-reviewed severity: "
            f"{reviewed or 'unavailable'}. "
            f"Recorded recommendation: "
            f"{action.replace('_', ' ') if action else 'unavailable'}."
        )

    return "\n\n" + "\n\n".join(sections)

def next_steps(context):
    pet = context.get("pet")

    if pet is None:
        return (
            "Start a pet-linked chat so I can check the right records.",
            "NONE",
        )

    name = pet["name"]
    latest = context.get("latest_analysis")

    if latest is None:
        return (
            f"I do not see a completed AI assessment uploaded "
            f"by you for {name}. You can open AI Scan to submit "
            "an image. If you already have concerns about your "
            "pet, contact a veterinarian without waiting for a scan.",
            "OPEN_AI_ANALYSIS",
        )

    reviews = [
        review
        for review in context.get("vet_reviews", [])
        if review["analysis_id"] == latest["analysis_id"]
    ]

    if reviews:
        feedback = vet_feedback(context, latest["analysis_id"])

        if len(reviews) > 1:
            return (
                "There are multiple recorded clinic reviews for "
                f"{name}'s latest assessment. Read each review "
                "separately and contact the reviewing clinic "
                "if their recommendations differ."
                + feedback,
                "OPEN_AI_ANALYSIS",
            )

        action = reviews[0].get("recommended_action")

        if action in {
            "routine_booking",
            "prompt_clinic_assessment",
        }:
            return (
                f"A veterinarian has recommended a clinic assessment "
                f"for {name}. Open Booking to check whether a visit "
                "is already booked. If not, choose a suitable time. "
                "For a review-linked booking, use Choose appointment "
                "time from that vet review."
                + feedback,
                "OPEN_APPOINTMENTS",
            )

        if action == "home_care":
            return (
                f"A veterinarian has recorded home-care guidance "
                f"for {name}. Follow the recorded instructions "
                "rather than treating the AI estimate as a new "
                "treatment plan. Contact the clinic if the condition "
                "changes or the instructions are unclear."
                + feedback,
                "OPEN_AI_ANALYSIS",
            )

        return (
            "The recorded review could not establish a clear "
            "assessment. Contact the reviewing clinic about "
            "an examination."
            + feedback,
            "OPEN_APPOINTMENTS",
        )

    severity = latest.get("estimated_severity")
    introduction = latest_description(name, latest)

    if severity == "inconclusive":
        return (
            introduction
            + " You can request a veterinary review of this "
            "assessment or submit another clear image. "
            "Do not use an inconclusive result to decide "
            "that treatment is unnecessary. Follow any "
            "existing veterinary instructions.",
            "OPEN_AI_ANALYSIS",
        )

    if severity in {"moderate", "severe"}:
        return (
            introduction
            + " Arrange a veterinary assessment rather than "
            "relying on this image estimate or dental products "
            "alone. Open Booking to check existing appointments "
            "before choosing another time.",
            "OPEN_APPOINTMENTS",
        )

    if severity == "mild":
        return (
            introduction
            + " You can request a vet review of this assessment "
            "for advice specific to your pet. A Mild estimate "
            "does not establish that home care alone is sufficient.",
            "OPEN_AI_ANALYSIS",
        )

    if severity == "none":
        return (
            introduction
            + " This image result does not rule out dental problems. "
            "Continue your vet's preventive-care advice and seek "
            "an assessment if you notice concerns.",
            "OPEN_AI_ANALYSIS",
        )

    return (
        introduction
        + " The severity value is unavailable. Request a vet "
        "review or contact your clinic instead of guessing "
        "what treatment is needed.",
        "OPEN_AI_ANALYSIS",
    )

def contextual_reply(intent, context):
    pet = context.get("pet")

    if pet is None:
        return (
            "Select a pet for this chat first. "
            "I can still answer general dental-care questions."
        )

    name = pet["name"]
    latest = context.get("latest_analysis")
    history = context.get("dental_history", [])

    if latest is None:
        return (
            f"I do not see a completed dental assessment "
            f"uploaded by you for {name}. "
            "You can submit a dental image from AI Scan."
        )

    if intent == "pet_prediction_scores":
        predictions = latest.get("predictions", [])

        if not predictions:
            return (
                f"No classification scores are saved for "
                f"{name}'s latest assessment."
            )

        lines = [
            f"Saved model scores for {name}, "
            f"assessment #{latest['analysis_id']} "
            f"({date_label(latest)}):"
        ]

        flagged = set()

        for prediction in predictions:
            condition = prediction["condition"]
            if (
                prediction.get("assessed", True) is not True
                or prediction.get("supported", True) is not True
                or type(prediction.get("positive")) is not bool
            ):
                lines.append(
                    f"• {condition.title()}: not assessed "
                    "for this species; this does not mean absent."
                )
                continue
                       
            score = prediction.get("confidence")
            positive = prediction.get("positive") is True

            if positive:
                flagged.add(condition)

            score_text = (
                f"{score * 100:.1f}%"
                if score is not None
                else "not recorded"
            )

            lines.append(
                f"• {condition.title()}: {score_text} "
                f"— model flag: {'yes' if positive else 'no'}"
            )

        lines.append(
            "These percentages are model scores, not disease "
            "severity or guaranteed diagnostic probabilities. "
            "A condition not flagged by the model is not proof "
            "that the condition is absent."
        )

        if (
            "healthy" in flagged
            and flagged & {"plaque", "gingivitis", "calculus"}
        ):
            lines.append(
                "The model flagged both Healthy and a dental "
                "condition. Treat this as mixed model output "
                "and request a veterinary review."
            )

        return (
            "\n".join(lines)
            + vet_feedback(context, latest["analysis_id"])
        )

    if intent == "pet_segmentation_values":
        segmentation = latest.get("segmentation", {})

        lines = [
            f"Saved segmentation estimates for {name}, "
            f"assessment #{latest['analysis_id']} "
            f"({date_label(latest)}):"
        ]

        available = False

        for key, label in (
            ("gingivitis_area_percent", "Gingivitis-related mask"),
            ("calculus_area_percent", "Calculus-related mask"),
        ):
            value = segmentation.get(key)

            if value is None:
                lines.append(f"• {label}: not recorded")
            else:
                available = True
                lines.append(
                    f"• {label}: approximately {value:.2f}% "
                    "of analysed image pixels"
                )

        if not available:
            lines.append(
                "This assessment has no saved area measurements. "
                "Missing measurements do not mean zero affected area."
            )

        lines.append(
            "These are model-estimated image regions, not the "
            "percentage of your pet's mouth affected or a clinical "
            "severity measurement. Masks can miss regions or "
            "highlight unrelated areas."
        )

        return "\n".join(lines)

    if intent == "explain_latest_analysis":
        return (
            latest_description(name, latest)
            + vet_feedback(context, latest["analysis_id"])
        )

    if intent == "explain_pet_severity":
        return (
            f"{name}'s assessment from {date_label(latest)} "
            f"has Estimated Severity: {severity_label(latest)}. "
            "This level comes from the system's estimation rules. "
            "It is separate from classification confidence "
            "and does not establish a clinical diagnosis."
            + vet_feedback(context, latest["analysis_id"])
        )

    if intent == "dental_analysis_history":
        lines = [
            f"Recent completed assessments for {name}:"
        ]

        for analysis in history:
            lines.append(
                f"• {date_label(analysis)} — "
                f"Estimated Severity: {severity_label(analysis)} "
                f"(assessment #{analysis['analysis_id']})."
            )

        lines.append(
            "These are AI assessment records, "
            "not the full consultation medical history."
        )

        return "\n".join(lines)

    if len(history) < 2:
        return (
            f"I need at least two completed assessments for "
            f"{name} before comparing the estimates."
        )

    previous = history[1]

    same_model = (
        latest.get("model_version") is not None
        and latest.get("model_version")
        == previous.get("model_version")
    )

    same_method = (
        latest.get("severity_method") is not None
        and latest.get("severity_method")
        == previous.get("severity_method")
    )

    comparison = (
        f"{name}'s previous assessment "
        f"({date_label(previous)}) recorded "
        f"{severity_label(previous)}; the latest "
        f"({date_label(latest)}) recorded "
        f"{severity_label(latest)}."
    )

    if not same_model or not same_method:
        return (
            comparison
            + " The model or estimation method differs, "
            "or its version is unavailable, so I cannot "
            "reliably interpret this as a severity trend."
        )

    ranks = {
        "none": 0,
        "mild": 1,
        "moderate": 2,
        "severe": 3,
    }

    old_rank = ranks.get(previous.get("estimated_severity"))
    new_rank = ranks.get(latest.get("estimated_severity"))

    if old_rank is None or new_rank is None:
        return (
            comparison
            + " A severity value is missing, "
            "so I cannot compare the levels."
        )

    change = (
        "lower"
        if new_rank < old_rank
        else "higher"
        if new_rank > old_rank
        else "unchanged"
    )

    return (
        comparison
        + f" The system-estimated level is {change}. "
        "Differences in lighting, angle and visible teeth "
        "can affect results. This does not confirm "
        "clinical improvement or deterioration."
    )

RESET_PHRASES = {
    "never mind",
    "nevermind",
    "forget that",
    "change topic",
    "change the topic",
    "new topic",
    "start over",
    "reset chat",
}

def is_topic_reset(message):
    text = " ".join(
        re.findall(r"[a-z0-9]+", message.casefold())
    )
    return text in RESET_PHRASES


PET_SWITCH_PHRASES = {
    "change pet",
    "switch pet",
    "select another pet",
    "switch to another pet",
    "i mean my other pet",
    "i meant my other pet",
    "this is about my other pet",
    "wrong pet",
}


def is_pet_switch(message):
    text = " ".join(
        re.findall(r"[a-z0-9]+", message.casefold())
    )
    return text in PET_SWITCH_PHRASES

def generate_contextual_reply(
    db,
    current_user,
    conversation,
    message,
    language="en",
):
    if is_topic_reset(message):
        return {
            "intent": "conversation_reset",
            "reply": (
                "Okay, let’s start a new topic. "
                "What would you like help with?"
            ),
            "mode": "rule",
            "sources": [],
            "similarity": None,
            "products": [],
            "suggested_questions": [],
            "recommended_action": "NONE",
            "context_reference": {
                "pet_id": conversation.pet_id,
                "topic_reset": True,
                "retrieved_at": (
                    datetime.now(timezone.utc).isoformat()
                ),
            },
        }

    answer = generate_reply(message)

    if answer.get("mode") != "rule" and is_pet_switch(message):
        return {
            "intent": "change_pet",
            "reply": (
                "Which pet do you mean? Tap Select pet below. "
                "A fresh conversation will open for your selection. "
                "Until then, this chat remains linked to its current pet."
            ),
            "mode": "rule",
            "sources": [],
            "similarity": None,
            "products": [],
            "suggested_questions": [],
            "recommended_action": "SELECT_PET",
            "context_reference": {
                "pet_id": conversation.pet_id,
                "topic_reset": True,
            },
        }

    if answer.get("mode") != "rule":
        explanation = explain_previous_products(
            db,
            conversation,
            message,
        )

        if explanation is not None:
            return explanation

    answer = dict(resolve_followup(
        db,
        conversation,
        message,
        answer,
    ))

    product_request = resolve_product_budget(
        db,
        conversation,
        message,
        answer,
    )

    if product_request is not None:
        answer["intent"] = "product_recommendation"

    intent = answer["intent"]

    reference = {
        "pet_id": conversation.pet_id,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }

    if intent in {
        "pet_medical_history",
        "recorded_prescriptions",
    }:
        answer["reply"] = medical_record_reply(
            db,
            current_user,
            conversation.pet_id,
            intent,
        )

        answer["recommended_action"] = (
            "OPEN_MEDICAL_HISTORY"
            if conversation.pet_id is not None
            else "NONE"
        )

    elif intent == "product_recommendation":
        products = []

        effective_request = product_request or message

        reference["product_request"] = effective_request

        reply, action = product_reply(
            db,
            current_user,
            conversation.pet_id,
            products=products,
            request_text=effective_request,
        )

        answer["reply"] = reply
        answer["products"] = products
        answer["recommended_action"] = action

    elif intent == "my_followup_care":
        answer["reply"] = followup_care_reply(
            db,
            current_user,
            conversation.pet_id,
        )

    elif intent == "upcoming_appointment":
        answer["reply"] = upcoming_appointment_reply(
            db,
            current_user,
            conversation.pet_id,
        )

    elif intent in CONTEXT_INTENTS:
        context = build_chat_context(
            db,
            current_user,
            conversation.pet_id,
        )

        if intent == "pet_next_steps":
            reply, action = next_steps(context)
            answer["reply"] = reply
            answer["recommended_action"] = action
        else:
            answer["reply"] = contextual_reply(
                intent,
                context,
            )

        if answer.get("mode") != "rule":
            translated_reply = _assessment_text.render_assessment_reply(
                intent, context, language
            )
            if translated_reply is not None:
                answer["reply"] = translated_reply

        latest = context.get("latest_analysis")

        reference = {
            "pet_id": conversation.pet_id,
            "analysis_id": (
                latest["analysis_id"]
                if latest is not None
                else None
            ),
            "assessment_job_id": (
                latest["assessment_job_id"]
                if latest is not None
                else None
            ),
            "retrieved_at": context["retrieved_at"],
        }

    else:
        # General FAQs and safety rules need no database context.
        return answer

    answer["context_reference"] = reference

    return answer