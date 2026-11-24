import re

from sqlalchemy import select

from app.models import ChatbotMessage
from app.services.chatbot_engine_service import generate_reply


TOPIC_QUESTIONS = {
    "explain_latest_analysis": "explain my latest result",
    "explain_pet_severity": "how severe is my pet condition",
    "dental_analysis_history": "show my pet previous results",
    "compare_analysis_progress": "compare with the previous result",
    "upcoming_appointment": "when is my next appointment",
    "explain_gradcam": "what does the heatmap mean",
    "explain_segmentation": "what does segmentation mean",
    "explain_confidence": "what is classification confidence",
    "plaque_information": "what is dental plaque",
    "gingivitis_information": "what is gingivitis",
    "calculus_information": "what is calculus",
    "book_appointment": "how do i book an appointment",
    "followup_update": "how do i send follow up photos",
    "my_followup_care": "show my pet follow up instructions",
    "product_recommendation": "recommend dental care products",
    "daily_dental_care": "how often should I brush my dog teeth",
    "brushing_technique": "how do I brush pet teeth",
    "bad_breath": "is bad breath normal",
    "dental_warning_signs": "what are signs of dental problems",
    "pet_medical_history": "show my pet medical history",
    "recorded_prescriptions": "show my pet recorded prescriptions",
    "pet_segmentation_values": "show my pet segmentation percentages",
    "pet_prediction_scores": "show my pet classification scores",
}

TOPIC_QUESTIONS.update({
    "pet_next_steps":
        "what should i do about my pet assessment",
})

ANALYSIS_TOPICS = {
    "explain_latest_analysis",
    "explain_pet_severity",
    "dental_analysis_history",
    "compare_analysis_progress",
    "pet_prediction_scores",
    "pet_segmentation_values",
    "pet_next_steps",
}


REPEAT_PHRASES = {
    "explain that",
    "explain it",
    "what does that mean",
    "tell me more about that",
    "repeat that",
}


PREVIOUS_PHRASES = {
    "what about the previous one",
    "what about before",
    "and the previous result",
}

SEVERITY_PHRASES = {
    "how severe is it",
    "and the severity",
    "what about its severity",
}


NEXT_STEP_PHRASES = {
    "what should i do",
    "what should i do now",
    "what should i do next",
    "what can i do",
    "what can i do next",
    "what is the next step",
    "what now",
    "any advice",
    "any recommendations",
    "then what",
}


TIME_PHRASES = {
    "when is it",
    "where is it",
    "which doctor",
    "which vet",
}

PREVIOUS_PHRASES.update({
    "what about my previous result",
    "what about the previous result",
    "show the earlier result",
})

TIME_PHRASES.update({
    "which clinic",
    "what time",
    "where is my appointment",
})


def clarification():
    return {
        "intent": "clarify",
        "reply": (
            "Which topic do you mean: your pet's AI result, "
            "estimated severity, previous assessment, appointment, "
            "heatmap or segmentation?"
        ),
        "mode": "fallback",
        "sources": [],
        "similarity": None,
    }

CHOICE_REPLIES = {
    "1": 0,
    "one": 0,
    "first": 0,
    "first one": 0,
    "the first one": 0,
    "option 1": 0,
    "2": 1,
    "two": 1,
    "second": 1,
    "second one": 1,
    "the second one": 1,
    "option 2": 1,
}

def remembered_topic(db, conversation):
    messages = db.scalars(
        select(ChatbotMessage)
        .where(
            ChatbotMessage.conversation_id
            == conversation.conversation_id,
            ChatbotMessage.sender_type == "assistant",
        )
        .order_by(ChatbotMessage.message_id.desc())
        .limit(20)
    ).all()

    for previous in messages:
        metadata = previous.response_metadata

        if not isinstance(metadata, dict):
            return None

        intent = metadata.get("intent")
        reference = metadata.get("context_reference")

        if not isinstance(reference, dict):
            reference = {}

        # Never carry a topic across an explicit reset or pet switch.
        if (
            intent in {"conversation_reset", "change_pet"}
            or reference.get("topic_reset") is True
        ):
            return None

        # Changing language does not change the conversation topic.
        if intent == "language_preference":
            continue

               # Safety responses must end the previous topic.
        if intent in {
            "urgent_vet_contact",
            "medication_referral",
            "human_toothpaste_warning",
        } or metadata.get("urgency_level"):
            return None

        # Allow recognised rule-based topics to be remembered.
        # Unknown rule responses remain topic boundaries.
        if (
            metadata.get("mode") == "rule"
            and intent not in TOPIC_QUESTIONS
        ):
            return None

        # Reject references explicitly linked to another pet.
        saved_pet_id = reference.get("pet_id")

        if (
            saved_pet_id is not None
            and saved_pet_id != conversation.pet_id
        ):
            return None

        # A clarification does not erase the previous topic.
        if intent == "clarify":
            continue

        if intent in TOPIC_QUESTIONS:
            return intent

        # Unknown topics are boundaries, not permission to guess.
        return None

    return None


def normalize_followup_text(message: str) -> str:
    text = message.casefold().strip()

    # Preserve English, Malay, numbers and Chinese.
    text = re.sub(
        r"[^\w\u3400-\u9fff]+",
        " ",
        text,
        flags=re.UNICODE,
    )

    return " ".join(text.split())



MULTILINGUAL_FOLLOWUPS = {
    # Chinese - severity
    "严重吗": "how severe is it",
    "会很严重吗": "how severe is it",
    "严重不严重": "how severe is it",

    # Malay - severity
    "bahaya ke": "how severe is it",
    "serius ke": "how severe is it",
    "adakah ia serius": "how severe is it",

    # Chinese - repeat/explain
    "再解释一次": "explain that",
    "可以再解释吗": "explain that",
    "再说明一下": "explain that",

    # Malay - repeat/explain
    "boleh terangkan lagi": "explain that",
    "boleh jelaskan lagi": "explain that",
    "terangkan lagi": "explain that",

    # Chinese - previous assessment
    "之前的结果呢": "what about the previous result",
    "上一次的结果呢": "what about the previous result",

    # Malay - previous assessment
    "keputusan sebelum ini": "what about the previous result",
}



def resolve_followup(db, conversation, message, answer):
    # Never replace an urgent, medication or other rule response.
    if answer.get("mode") == "rule":
        return answer
    
    text = normalize_followup_text(message)

    text = MULTILINGUAL_FOLLOWUPS.get(
        text,
        text,
    )

    followup_phrases = (
        REPEAT_PHRASES
        | PREVIOUS_PHRASES
        | SEVERITY_PHRASES
        | TIME_PHRASES
        | NEXT_STEP_PHRASES
    )

    is_choice = text in CHOICE_REPLIES

    if text not in followup_phrases and not is_choice:
        return answer

    previous = db.scalar(
        select(ChatbotMessage)
        .where(
            ChatbotMessage.conversation_id
            == conversation.conversation_id,
            ChatbotMessage.sender_type == "assistant",
        )
        .order_by(ChatbotMessage.message_id.desc())
        .limit(1)
    )

    if previous is None:
        return clarification()

    metadata = previous.response_metadata

    if not isinstance(metadata, dict):
        return clarification()

    if is_choice:
        choices = metadata.get("suggested_questions")

        if (
            metadata.get("intent") != "clarify"
            or not isinstance(choices, list)
        ):
            return answer

        index = CHOICE_REPLIES[text]

        if index >= len(choices):
            return {
                "intent": "clarify",
                "reply": (
                    "That option is not available. "
                    "Please tap one of the suggested questions."
                ),
                "mode": "fallback",
                "sources": [],
                "similarity": None,
                "suggested_questions": choices[:2],
            }

        question = choices[index]

        if (
            not isinstance(question, str)
            or not 1 <= len(question.strip()) <= 200
        ):
            return clarification()

        return generate_reply(question)

    previous_intent = remembered_topic(db, conversation)
    canonical_question = None

    if text in REPEAT_PHRASES:
        canonical_question = TOPIC_QUESTIONS.get(
            previous_intent
        )

    elif text in PREVIOUS_PHRASES:
        if previous_intent in ANALYSIS_TOPICS:
            canonical_question = "show my pet previous results"

    elif text in SEVERITY_PHRASES:
        if previous_intent in ANALYSIS_TOPICS:
            canonical_question = "how severe is my pet condition"

    elif text in NEXT_STEP_PHRASES:
        if previous_intent in ANALYSIS_TOPICS:
            canonical_question = (
                "what should i do about my pet assessment"
            )

    elif text in TIME_PHRASES:
        if previous_intent == "upcoming_appointment":
            canonical_question = "when is my next appointment"

    if canonical_question is None:
        return clarification()

    # Resolve the topic through the existing hybrid engine.
    # The normal contextual service retrieves fresh pet records.
    return generate_reply(canonical_question)