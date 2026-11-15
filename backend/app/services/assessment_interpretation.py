CONDITIONS = {
    "healthy",
    "plaque",
    "gingivitis",
    "calculus",
}


def normalize_assessment(summary):
    if not isinstance(summary, dict):
        return {}

    result = dict(summary)
    predictions = result.get("predictions")

    # Retain the original experimental estimate for traceability.
    original = result.get(
        "experimental_severity",
        result.get("severity"),
    )

    result["experimental_severity"] = (
        dict(original)
        if isinstance(original, dict)
        else None
    )

    decisions = {}

    if isinstance(predictions, list):
        for item in predictions:
            if not isinstance(item, dict):
                continue

            condition = item.get("condition")

            if condition not in CONDITIONS:
                continue

            if (
                condition in decisions
                or type(item.get("positive")) is not bool
            ):
                decisions = {}
                break

            decisions[condition] = item["positive"]

    if set(decisions) != CONDITIONS:
        status = "unavailable"
        label = "Unavailable"
        reason = "The prediction decisions are incomplete."
        diseases = []

    else:
        diseases = sorted(
            condition
            for condition, positive in decisions.items()
            if condition != "healthy" and positive
        )

        healthy = decisions["healthy"]

        if healthy and diseases:
            status = "inconclusive"
            label = "Inconclusive"
            reason = (
                "Healthy and disease predictions both passed "
                "their thresholds. No overall severity is assigned."
            )

        elif not healthy and not diseases:
            status = "inconclusive"
            label = "Inconclusive"
            reason = (
                "No classification passed its threshold. "
                "This does not establish a healthy condition."
            )

        elif healthy:
            status = "healthy_pattern"
            label = "None"
            reason = (
                "Only the healthy classification passed its threshold. "
                "This is a screening result, not confirmation of health."
            )

        else:
            status = "disease_flags"
            estimate = (
                original
                if isinstance(original, dict)
                else {}
            )

            label = estimate.get("label")

            if label not in {"Mild", "Moderate", "Severe"}:
                label = "Unavailable"

            reason = (
                estimate.get("reason")
                or "Disease classifications passed their thresholds."
            )

    result["decision"] = {
        "version": "screening-decision-v1",
        "status": status,
        "disease_flags": diseases,
        "reason": reason,
    }

    result["severity"] = {
        "label": label,
        "method": (
            "experimental_rule_based"
            if status == "disease_flags"
            else "not_assigned"
        ),
        "reason": reason,
    }

    return result