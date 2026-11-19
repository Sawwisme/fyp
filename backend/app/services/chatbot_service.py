from datetime import datetime, timezone
import json
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import ChatbotConversation, ChatbotMessage
from app.services.chatbot_answer_service import (
    generate_contextual_reply,
)
from app.services.pet_service import get_owner_profile, get_pet

from app.services.chatbot_engine_service import load_chatbot_module

multilingual_safety_reply = load_chatbot_module(
    "chatbot_safety"
).multilingual_safety_reply

from app.services.chatbot_language_service import (
    requested_language,
    saved_language,
    language_preference_reply,
    prepare_multilingual_question,
    localize_faq_answer,
)

CHAT_ACTIONS = {
    "explain_latest_analysis": "OPEN_AI_ANALYSIS",
    "explain_pet_severity": "OPEN_AI_ANALYSIS",
    "dental_analysis_history": "OPEN_AI_ANALYSIS",
    "compare_analysis_progress": "OPEN_AI_ANALYSIS",
    "explain_gradcam": "OPEN_AI_ANALYSIS",
    "explain_segmentation": "OPEN_AI_ANALYSIS",
    "request_review": "OPEN_AI_ANALYSIS",
    "book_appointment": "OPEN_APPOINTMENT_BOOKING",
    "upcoming_appointment": "OPEN_APPOINTMENTS",
    "cancel_appointment": "OPEN_APPOINTMENTS",
    "my_followup_care": "OPEN_FOLLOWUP_CARE",
    "followup_update": "OPEN_FOLLOWUP_CARE",
    "pet_segmentation_values": "OPEN_AI_ANALYSIS",
    "pet_prediction_scores": "OPEN_AI_ANALYSIS",
}

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def timestamp(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def require_owner(db, current_user):
    if current_user.role != "pet_owner":
        raise HTTPException(
            403,
            "A pet owner account is required.",
        )

    return get_owner_profile(db, current_user)


def conversation_dict(record):
    return {
        "conversation_id": record.conversation_id,
        "pet_id": record.pet_id,
        "pet_name": (
            record.pet.pet_name
            if record.pet is not None
            else None
        ),
        "booking_draft": record.booking_draft,
        "booking_draft_revision": record.booking_draft_revision,
        "status": record.status,
        "started_at": timestamp(record.started_at),
        "ended_at": timestamp(record.ended_at),
    }


def message_dict(record):
    return {
        "message_id": record.message_id,
        "conversation_id": record.conversation_id,
        "sender_type": record.sender_type,
        "message_text": record.message_text,
        "client_request_id": record.client_request_id,
        "sent_at": timestamp(record.sent_at),
        "response_metadata": record.response_metadata or {},
    }


def owned_conversation(
    db,
    current_user,
    conversation_id,
    lock=False,
):
    require_owner(db, current_user)

    statement = (
        select(ChatbotConversation)
        .where(
            ChatbotConversation.conversation_id
            == conversation_id,
            ChatbotConversation.user_id
            == current_user.user_id,
        )
        .options(selectinload(ChatbotConversation.pet))
    )

    if lock:
        statement = (
            statement
            .execution_options(populate_existing=True)
            .with_for_update()
        )

    conversation = db.scalar(statement)

    if conversation is None:
        raise HTTPException(
            404,
            "Conversation not found.",
        )

    return conversation


def create_conversation(db, current_user, data):
    try:
        require_owner(db, current_user)

        if data.pet_id is not None:
            get_pet(db, current_user, data.pet_id)

        conversation = ChatbotConversation(
            user_id=current_user.user_id,
            pet_id=data.pet_id,
            status="active",
            started_at=utc_now(),
        )

        db.add(conversation)
        db.flush()

        response = conversation_dict(conversation)

        db.commit()
        return response

    except Exception:
        db.rollback()
        raise


def list_conversations(
    db,
    current_user,
    offset,
    limit,
):
    require_owner(db, current_user)

    conversations = db.scalars(
        select(ChatbotConversation)
        .where(
            ChatbotConversation.user_id
            == current_user.user_id,
        )
        .options(selectinload(ChatbotConversation.pet))
        .order_by(
            ChatbotConversation.started_at.desc(),
            ChatbotConversation.conversation_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        conversation_dict(record)
        for record in conversations
    ]


def get_conversation(db, current_user, conversation_id):
    return conversation_dict(
        owned_conversation(
            db,
            current_user,
            conversation_id,
        )
    )


def list_messages(
    db,
    current_user,
    conversation_id,
    before_message_id,
    limit,
):
    owned_conversation(
        db,
        current_user,
        conversation_id,
    )

    statement = select(ChatbotMessage).where(
        ChatbotMessage.conversation_id == conversation_id,
    )

    if before_message_id is not None:
        statement = statement.where(
            ChatbotMessage.message_id < before_message_id,
        )

    # Fetch the latest page, then return it in reading order.
    records = list(
        db.scalars(
            statement
            .order_by(ChatbotMessage.message_id.desc())
            .limit(limit + 1)
        ).all()
    )

    has_more = len(records) > limit
    records = list(reversed(records[:limit]))

    return {
        "items": [
            message_dict(record)
            for record in records
        ],
        "has_more": has_more,
        "next_before_message_id": (
            records[0].message_id
            if has_more and records
            else None
        ),
    }


def send_message(
    db,
    current_user,
    conversation_id,
    data,
):
    try:
        # Serialize sends within this conversation.
        conversation = owned_conversation(
            db,
            current_user,
            conversation_id,
            lock=True,
        )

        request_id = str(data.client_request_id)
        message = data.message.strip()

        # Locking read sees committed messages after a concurrent retry.
        previous = list(
            db.scalars(
                select(ChatbotMessage)
                .where(
                    ChatbotMessage.conversation_id
                    == conversation_id,
                    ChatbotMessage.client_request_id
                    == request_id,
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            ).all()
        )

        if previous:
            by_sender = {
                record.sender_type: record
                for record in previous
            }

            if (
                len(previous) != 2
                or set(by_sender) != {"user", "assistant"}
            ):
                raise HTTPException(
                    409,
                    "The previous message pair is incomplete. "
                    "Reload the conversation.",
                )

            if by_sender["user"].message_text != message:
                raise HTTPException(
                    409,
                    "This request ID was already used "
                    "for a different message.",
                )

            response = {
                "conversation_id": conversation_id,
                "messages": [
                    message_dict(by_sender["user"]),
                    message_dict(by_sender["assistant"]),
                ],
                "replayed": True,
            }

            db.commit()
            return response

        if conversation.status != "active":
            raise HTTPException(
                409,
                "This conversation is closed. Start a new chat.",
            )

        language = saved_language(db, conversation)

        # Check the original message before FAQ translation,
        # topic recall or language-switch handling.
        safety_answer = multilingual_safety_reply(
            message,
            preferred_language=language,
        )

        if safety_answer is not None:
            answer = safety_answer
            language = answer["language"]

        else:
            language_request = requested_language(message)

            if language_request is not None:
                language = language_request
                answer = language_preference_reply(language)
            else:
                engine_message, language = (
                    prepare_multilingual_question(
                        message,
                        language,
                    )
                )

                answer = generate_contextual_reply(
                    db,
                    current_user,
                    conversation,
                    engine_message,
                    language=language,
                )

                answer = localize_faq_answer(
                    answer,
                    language,
                )

        answer["language"] = language
        now = utc_now()

        user_message = ChatbotMessage(
            conversation_id=conversation_id,
            sender_type="user",
            message_text=message,
            client_request_id=request_id,
            sent_at=now,
        )

        db.add(user_message)
        db.flush()

        assistant_message = ChatbotMessage(
            conversation_id=conversation_id,
            sender_type="assistant",
            message_text=answer["reply"],
            client_request_id=request_id,
            response_metadata={
                "intent": answer["intent"],
                "language": answer["language"],
                "urgency_level": answer.get("urgency_level"),
                "suggested_questions": (
                    answer.get("suggested_questions", [])
                    if answer["intent"] == "clarify"
                    else []
                ),
                "mode": answer["mode"],
                "sources": answer["sources"],
                "similarity": answer["similarity"],
                "context_reference": answer.get("context_reference"),
                "products": answer.get("products", []),
                "recommended_action": answer.get(
                    "recommended_action",
                    CHAT_ACTIONS.get(answer["intent"], "NONE"),
                ),
            },
            sent_at=now,
        )

        db.add(assistant_message)
        db.flush()

        response = {
            "conversation_id": conversation_id,
            "messages": [
                message_dict(user_message),
                message_dict(assistant_message),
            ],
            "replayed": False,
        }

        db.commit()
        return response

    except Exception:
        db.rollback()
        raise


def close_conversation(
    db,
    current_user,
    conversation_id,
):
    try:
        conversation = owned_conversation(
            db,
            current_user,
            conversation_id,
            lock=True,
        )

        if conversation.status != "closed":
            conversation.status = "closed"
            conversation.ended_at = utc_now()

        response = conversation_dict(conversation)

        db.commit()
        return response

    except Exception:
        db.rollback()
        raise

def save_booking_draft(
    db, current_user, conversation_id, data
):
    try:
        conversation = owned_conversation(
            db,
            current_user,
            conversation_id,
            lock=True,
        )

        if conversation.status != "active":
            raise HTTPException(409, "This conversation is closed.")

        if conversation.booking_draft_revision != data.expected_revision:
            raise HTTPException(
                409,
                "Booking draft changed. Reload this conversation.",
            )

        draft = data.draft

        if draft is not None:
            try:
                encoded = json.dumps(
                    draft,
                    ensure_ascii=False,
                    allow_nan=False,
                )
            except (TypeError, ValueError, RecursionError):
                raise HTTPException(422, "Invalid booking draft.")

            if len(encoded.encode("utf-8")) > 16384:
                raise HTTPException(422, "Booking draft is too large.")

            if (
                draft.get("schema_version") != 1
                or draft.get("conversation_id") != conversation_id
                or draft.get("pet_context_id") != conversation.pet_id
            ):
                raise HTTPException(
                    422,
                    "Booking draft does not match this conversation.",
                )

            state = draft.get("state")
            if not isinstance(state, dict):
                raise HTTPException(422, "Invalid booking state.")

            selected_pet = state.get("pet")
            if selected_pet is not None:
                if not isinstance(selected_pet, dict):
                    raise HTTPException(422, "Invalid selected pet.")

                selected_pet_id = selected_pet.get("pet_id")
                if type(selected_pet_id) is not int:
                    raise HTTPException(422, "Invalid selected pet.")

                get_pet(db, current_user, selected_pet_id)

                if (
                    conversation.pet_id is not None
                    and selected_pet_id != conversation.pet_id
                ):
                    raise HTTPException(
                        422,
                        "Selected pet differs from this chat's pet.",
                    )

        conversation.booking_draft = draft
        conversation.booking_draft_revision += 1
        db.flush()

        response = conversation_dict(conversation)
        db.commit()
        return response

    except Exception:
        db.rollback()
        raise