import re

from sqlalchemy import select

from app.models import ChatbotMessage


BUDGET_PATTERN = (
    r"\b(?:under|below|up to|maximum|max|budget)"
    r"\s*(?:of\s*)?(?:rm\s*)?"
    r"\d+(?:\.\d{1,2})?(?![\d.])"
)

BUDGET_REPLY = re.compile(
    BUDGET_PATTERN
    + r"(?:\s*(?:please|pls|thanks))?[!]?",
    re.IGNORECASE,
)

CARE_REPLIES = {
    "brushing": "routine brushing",
    "routine brushing": "routine brushing",
    "oral hygiene": "oral hygiene",
    "routine dental care": "routine dental care",
    "plaque": "plaque control",
    "plaque control": "plaque control",
    "plaque prevention": "plaque prevention",
    "breath": "breath care",
    "breath care": "breath care",
    "bad breath": "breath care",
    "breath freshening": "breath freshening",
}


def resolve_product_budget(db, conversation, message, answer):
    # Keep the existing function name so the caller stays unchanged.
    text = message.strip()

    care_key = re.sub(
        r"\s+(please|pls|thanks)$",
        "",
        text.lower().rstrip(".!"),
    ).strip()

    care_reply = CARE_REPLIES.get(care_key)
    budget_reply = BUDGET_REPLY.fullmatch(text)

    if care_reply is None and budget_reply is None:
        return None

    allowed_intents = {
        "clarify",
        "product_recommendation",
    }

    if care_reply is not None:
        allowed_intents.update({
            "daily_dental_care",
            "brushing_technique",
            "bad_breath",
            "plaque_information",
        })

    # Do not replace unrelated or safety-related responses.
    if answer.get("intent") not in allowed_intents:
        return None

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
        return None

    metadata = previous.response_metadata or {}

    if metadata.get("intent") != "product_recommendation":
        return None

    reference = metadata.get("context_reference") or {}

    if reference.get("pet_id") != conversation.pet_id:
        return None

    previous_request = reference.get("product_request")

    if not isinstance(previous_request, str):
        return None

    if care_reply is not None:
        # A new care-purpose selection replaces the earlier purpose.
        # Preserve the previously requested budget.
        previous_budget = re.search(
            BUDGET_PATTERN,
            previous_request,
            flags=re.IGNORECASE,
        )

        parts = [
            "Recommend products for " + care_reply,
        ]

        if previous_budget:
            parts.append(previous_budget.group(0))

        return "\n".join(parts)[:2000]

    # A new budget replaces the earlier budget.
    previous_request = re.sub(
        BUDGET_PATTERN,
        "",
        previous_request,
        flags=re.IGNORECASE,
    ).strip()

    return f"{text}\n{previous_request}"[:2000]