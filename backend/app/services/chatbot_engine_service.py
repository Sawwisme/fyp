import logging
import math
import sys
from functools import lru_cache
from importlib import import_module
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def get_chatbot():
    project_path = str(PROJECT_ROOT)

    if project_path not in sys.path:
        sys.path.insert(0, project_path)

    module = import_module("ai.chatbot.chatbot_engine")
    return module.chatbot


def validate_answer(answer):
    if not isinstance(answer, dict):
        raise ValueError("Invalid chatbot response.")

    if (
        not isinstance(answer.get("intent"), str)
        or not isinstance(answer.get("reply"), str)
        or not answer["reply"].strip()
        or answer.get("mode") not in {
            "rule", "nlp", "fallback"
        }
    ):
        raise ValueError("Invalid answer fields.")

    sources = answer.get("sources", [])

    if not isinstance(sources, list):
        raise ValueError("Invalid sources.")

    for source in sources:
        if not isinstance(source, str):
            raise ValueError("Invalid source URL.")

        parsed = urlsplit(source)

        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("Invalid source URL.")

    similarity = answer.get("similarity")

    if similarity is not None:
        if (
            isinstance(similarity, bool)
            or not isinstance(similarity, (int, float))
            or not math.isfinite(similarity)
            or not 0 <= similarity <= 1
        ):
            raise ValueError("Invalid similarity score.")

    suggestions = answer.get("suggested_questions", [])

    if (
        not isinstance(suggestions, list)
        or len(suggestions) > 2
        or any(
            not isinstance(question, str)
            or not 1 <= len(question.strip()) <= 200
            for question in suggestions
        )
    ):
        raise ValueError("Invalid suggested questions.")

    return {
        "intent": answer["intent"],
        "reply": answer["reply"],
        "mode": answer["mode"],
        "sources": list(sources),
        "similarity": similarity,
        "suggested_questions": (
            list(suggestions)
            if answer["intent"] == "clarify"
            else []
        ),
    }


def generate_reply(message):
    if (
        not isinstance(message, str)
        or not 1 <= len(message.strip()) <= 2000
    ):
        raise HTTPException(
            status_code=422,
            detail="Enter a message between 1 and 2000 characters.",
        )

    try:
        answer = get_chatbot().answer(message.strip())
        return validate_answer(answer)

    except Exception:
        logger.exception("Chatbot response generation failed.")

        raise HTTPException(
            status_code=503,
            detail="The chatbot could not respond. Please try again.",
        ) from None