"""Controlled product metadata for chatbot recommendations."""

ALLOWED_RECOMMENDATION_TAGS = {
    "routine_oral_hygiene",
    "plaque_control",
    "breath_freshening",
}


def validate_recommendation_tags(value):
    if value is None:
        return []

    if not isinstance(value, list):
        raise ValueError("Recommendation tags must be a list.")

    if any(not isinstance(item, str) for item in value):
        raise ValueError("Each recommendation tag must be text.")

    tags = sorted({
        item.strip().lower()
        for item in value
        if item.strip()
    })

    unsupported = set(tags) - ALLOWED_RECOMMENDATION_TAGS

    if unsupported:
        raise ValueError(
            "Unsupported recommendation tags: "
            + ", ".join(sorted(unsupported))
        )

    return tags

def match_care_tags(value):
    import re

    text = (value or "").lower()

    # Free-text restrictions and uncertainty need interpretation.
    # Do not silently override them with keyword matches.
    if re.search(
        r"\b(no|not|avoid|without|stop|contraindicated|"
        r"unless|suspected|possible|rule out)\b",
        text,
    ):
        return set()

    patterns = {
        "routine_oral_hygiene": (
            r"\b(brush|brushing|toothbrush|toothpaste|"
            r"oral hygiene|routine dental care)\b"
        ),
        "plaque_control": (
            r"\b(plaque control|plaque prevention|"
            r"control plaque|prevent plaque|reduce plaque)\b"
        ),
        "breath_freshening": (
            r"\b(breath freshening|freshen breath|"
            r"bad breath|breath care)\b"
        ),
    }

    return {
        tag
        for tag, pattern in patterns.items()
        if re.search(pattern, text)
    }

def build_product_match(context, request_text):
    import re

    consultation = context.get("latest_consultation")

    if not consultation:
        return {
            "source": "Your request",
            "tags": match_care_tags(request_text),
            "explanation": (
                "Matched to your requested care purpose, "
                "not a confirmed diagnosis."
            ),
            "blocked_reason": None,
        }

    diagnosis = (
        consultation.get("diagnosis") or ""
    ).strip()

    instructions = (
        consultation.get("home_care_instructions") or ""
    ).strip()

    source = (
        f"Consultation #{consultation['consultation_id']}"
    )

    combined = f"{diagnosis}\n{instructions}".lower()

    # Conservative handling of restrictions and complex cases.
    # This is not a complete clinical language interpreter.
    restricted = re.search(
        r"\b(no|not|avoid|without|stop|contraindicated|"
        r"unless|suspected|possible|rule out|"
        r"pain|painful|bleeding|ulcer|ulcers|"
        r"extraction|extractions|surgery|"
        r"postoperative|post-operative|"
        r"fracture|fractured|abscess|"
        r"periodontitis|stomatitis|severe)\b",
        combined,
    )

    if restricted:
        return {
            "source": source,
            "tags": set(),
            "explanation": "",
            "blocked_reason": (
                "Your consultation contains a restriction, "
                "uncertainty, or a condition requiring more "
                "individual guidance. I have not automatically "
                "selected care products. Follow the recorded "
                "instructions and contact your clinic if needed."
            ),
        }

    diagnosis_text = diagnosis.lower()
    diagnosis_tags = set()
    notes = []

    if re.search(r"\bplaque\b", diagnosis_text):
        diagnosis_tags.add("plaque_control")
        notes.append(
            "The consultation records plaque. Matching products "
            "are labelled for plaque control."
        )

    if re.search(r"\bgingivitis\b", diagnosis_text):
        diagnosis_tags.add("plaque_control")
        notes.append(
            "The consultation records gingivitis. Plaque-control "
            "products are shown as supportive home-care options, "
            "not as treatment for gum inflammation."
        )

    if re.search(r"\b(calculus|tartar)\b", diagnosis_text):
        diagnosis_tags.add("plaque_control")
        notes.append(
            "The consultation records calculus or tartar. "
            "Plaque-control products are preventive care options; "
            "they are not presented as removing existing calculus."
        )

    if re.search(
        r"\b(healthy|normal dentition|normal oral examination)\b",
        diagnosis_text,
    ):
        diagnosis_tags.add("routine_oral_hygiene")
        notes.append(
            "The consultation records a healthy or normal finding. "
            "Matching products support routine oral hygiene."
        )

    instruction_tags = match_care_tags(instructions)

    # Explicit care instructions narrow the matching purpose.
    # Otherwise use the supported diagnosis mapping.
    tags = instruction_tags or diagnosis_tags

    if instruction_tags:
        notes.append(
            "The recorded home-care instructions were used "
            "to select the care purpose."
        )

    return {
        "source": source,
        "tags": tags,
        "explanation": " ".join(notes),
        "blocked_reason": None,
    }