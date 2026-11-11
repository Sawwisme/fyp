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


ANALYSIS_TOPICS = {
    "explain_latest_analysis",
    "explain_pet_severity",
    "dental_analysis_history",
    "compare_analysis_progress",
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


TIME_PHRASES = {
    "when is it",
    "where is it",
    "which doctor",
    "which vet",
}


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


def resolve_followup(db, conversation, message, answer):
    # Never replace an urgent, medication or other rule response.
    if answer.get("mode") == "rule":
        return answer

    text = " ".join(
        re.findall(r"[a-z0-9]+", message.casefold())
    )

    followup_phrases = (
        REPEAT_PHRASES
        | PREVIOUS_PHRASES
        | SEVERITY_PHRASES
        | TIME_PHRASES
    )

    if text not in followup_phrases:
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

    previous_intent = metadata.get("intent")
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

    elif text in TIME_PHRASES:
        if previous_intent == "upcoming_appointment":
            canonical_question = "when is my next appointment"

    if canonical_question is None:
        return clarification()

    # Resolve the topic through the existing hybrid engine.
    # The normal contextual service retrieves fresh pet records.
    return generate_reply(canonical_question)