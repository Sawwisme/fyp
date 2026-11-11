import json
import sys

from chatbot_engine import chatbot


def main():
    try:
        raw = sys.stdin.read(16385)

        if len(raw) > 16384:
            raise ValueError("Request is too large.")

        data = json.loads(raw)

        if not isinstance(data, dict) or set(data) != {"message"}:
            raise ValueError("Provide a message.")

        answer = chatbot.answer(data["message"])

        print(json.dumps(
            {
                "status": "completed",
                "answer": answer,
            },
            ensure_ascii=False,
            allow_nan=False,
        ))

        return 0

    except (ValueError, TypeError):
        print(json.dumps({
            "status": "rejected",
            "message": "Enter a message between 1 and 2000 characters.",
        }))
        return 2

    except Exception as error:
        print(
            f"Chatbot runner failed: {type(error).__name__}",
            file=sys.stderr,
        )

        print(json.dumps({
            "status": "failed",
            "message": "The chatbot could not respond.",
        }))

        return 1


if __name__ == "__main__":
    raise SystemExit(main())