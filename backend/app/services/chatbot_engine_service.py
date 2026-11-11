import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException


logger = logging.getLogger(__name__)

RUNNER = (
    Path(__file__).resolve().parents[3]
    / "ai"
    / "chatbot"
    / "chatbot_runner.py"
)


def generate_reply(message):
    if (
        not isinstance(message, str)
        or not 1 <= len(message.strip()) <= 2000
    ):
        raise HTTPException(
            422,
            "Enter a message between 1 and 2000 characters.",
        )

    if not RUNNER.is_file():
        raise HTTPException(
            503,
            "The chatbot is not configured.",
        )

    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(RUNNER),
            ],
            input=json.dumps(
                {"message": message.strip()},
                ensure_ascii=False,
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=8,
            cwd=str(RUNNER.parent),
            env=environment,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
            check=False,
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            503,
            "The chatbot took too long. Please try again.",
        ) from None

    except OSError:
        logger.exception("Could not start chatbot runner.")

        raise HTTPException(
            503,
            "The chatbot is temporarily unavailable.",
        ) from None

    try:
        payload = json.loads(result.stdout)

        if (
            result.returncode != 0
            or not isinstance(payload, dict)
            or payload.get("status") != "completed"
        ):
            raise ValueError("Unsuccessful chatbot response.")

        answer = payload["answer"]

        if not isinstance(answer, dict):
            raise ValueError("Invalid answer.")

        if (
            not isinstance(answer.get("intent"), str)
            or not isinstance(answer.get("reply"), str)
            or not answer["reply"].strip()
            or answer.get("mode") not in {
                "rule",
                "nlp",
                "fallback",
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

        if similarity is not None and (
            isinstance(similarity, bool)
            or not isinstance(similarity, (int, float))
            or not 0 <= similarity <= 1
        ):
            raise ValueError("Invalid similarity score.")

        return {
            "intent": answer["intent"],
            "reply": answer["reply"],
            "mode": answer["mode"],
            "sources": sources,
            "similarity": similarity,
        }

    except (ValueError, KeyError, TypeError):
        logger.error(
            "Invalid chatbot runner response; exit code %s.",
            result.returncode,
        )

        raise HTTPException(
            503,
            "The chatbot could not respond. Please try again.",
        ) from None