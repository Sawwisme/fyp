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

        # Simplified Chinese
    "日常刷牙": "routine brushing",
    "刷牙": "routine brushing",
    "日常刷牙用品": "routine brushing",
    "日常护理": "routine dental care",
    "日常牙齿护理": "routine dental care",
    "口腔卫生": "oral hygiene",
    "牙菌斑": "plaque control",
    "牙菌斑控制": "plaque control",
    "预防牙菌斑": "plaque prevention",
    "口气护理": "breath care",
    "口臭": "breath care",
    "清新口气": "breath freshening",

    # Bahasa Melayu
    "memberus gigi": "routine brushing",
    "berus gigi": "routine brushing",
    "gosok gigi": "routine brushing",
    "memberus gigi harian": "routine brushing",
    "penjagaan gigi harian": "routine dental care",
    "kebersihan mulut": "oral hygiene",
    "kawalan plak": "plaque control",
    "plak": "plaque control",
    "pencegahan plak": "plaque prevention",
    "penjagaan nafas": "breath care",
    "nafas berbau": "breath care",
    "bau mulut": "breath care",
}


def resolve_product_budget(db, conversation, message, answer):
    # Keep the existing function name so the caller stays unchanged.
    text = message.strip()

    care_key = re.sub(
        r"\s+(please|pls|thanks)$",
        "",
    text.casefold().rstrip(".!。！?？"),
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

def explain_previous_products(
    db, conversation, message, *, language="en"
):
    text = " ".join(
        re.sub(
            r"[^\w\s]|_",
            " ",
            message.casefold(),
        ).split()
    )

    supported = {
        "why this product",
        "why these products",
        "why recommend this",
        "why did you recommend these",
        "explain these recommendations",
        "kenapa produk ini",
        "mengapa produk ini",
        "kenapa cadangkan produk ini",
        "jelaskan cadangan produk ini",
        "为什么推荐这个产品",
        "为什么推荐这些产品",
        "为什么推荐这些",
        "解释这些推荐",
    }

    if text not in supported:
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
    reference = metadata.get("context_reference") or {}

    if reference.get("pet_id") != conversation.pet_id:
        return None

    previous_intent = metadata.get("intent")

    if previous_intent == "product_recommendation":
        products = metadata.get("products") or []
    elif previous_intent == "product_explanation":
        products = reference.get("explained_products") or []
    else:
        return None

    if not isinstance(products, list) or not products:
        return None

    snapshots = []
    headings = {
        "en": "Why the previously shown products matched:",
        "ms": "Sebab produk yang dipaparkan sebelum ini sepadan:",
        "zh": "之前展示的产品为何匹配：",
    }
    sections = [headings.get(language, headings["en"])]

    for product in products[:6]:
        if not isinstance(product, dict):
            continue

        name = product.get("product_name")
        reason = product.get("recommendation_reason")

        if not isinstance(name, str) or not isinstance(reason, str):
            continue

        snapshots.append({
            "product_name": name,
            "recommendation_reason": reason,
        })

        sections.append(f"• {name}\n{reason}")

    if not snapshots:
        return None

    notices = {
        "en": (
            "The saved matching reasons are reproduced as originally shown. "
            "Price, stock and suitability information may change. "
            "These suggestions do not replace prescribed treatment."
        ),
        "ms": (
            "Sebab padanan tersimpan dipaparkan seperti asal. "
            "Harga, stok dan maklumat kesesuaian mungkin berubah. "
            "Cadangan ini tidak menggantikan rawatan yang dipreskripsikan."
        ),
        "zh": (
            "已保存的匹配理由按当时展示的原文保留。"
            "价格、库存和适用信息可能变化。"
            "这些建议不能替代已开具的治疗方案。"
        ),
    }
    sections.append(notices.get(language, notices["en"]))

    return {
        "intent": "product_explanation",
        "reply": "\n\n".join(sections),
        "mode": "rule",
        "sources": [],
        "similarity": None,
        "products": [],
        "suggested_questions": [],
        "recommended_action": "NONE",
        "context_reference": {
            "pet_id": conversation.pet_id,
            "explained_products": snapshots,
        },
    }