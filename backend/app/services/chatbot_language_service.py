"""Database-backed language preference; reusable language rules live in ai/chatbot."""
from sqlalchemy import select
from app.models import ChatbotMessage
from app.services.chatbot_engine_service import load_chatbot_module

_language = load_chatbot_module("chatbot_language")
render_upcoming_appointments = _language.render_upcoming_appointments
render_followup_care = _language.render_followup_care
render_product_match_reason = _language.render_product_match_reason
render_product_search_reply = _language.render_product_search_reply
SUPPORTED_LANGUAGES = _language.SUPPORTED_LANGUAGES
requested_language = _language.requested_language
language_preference_reply = _language.language_preference_reply
prepare_multilingual_question = _language.prepare_multilingual_question
localize_faq_answer = _language.localize_faq_answer

def saved_language(db, conversation):
    previous = db.scalar(select(ChatbotMessage).where(ChatbotMessage.conversation_id == conversation.conversation_id, ChatbotMessage.sender_type == 'assistant').order_by(ChatbotMessage.message_id.desc()).limit(1))
    if previous is None:
        return 'en'
    metadata = previous.response_metadata
    if not isinstance(metadata, dict):
        return 'en'
    language = metadata.get('language')
    return language if language in SUPPORTED_LANGUAGES else 'en'
