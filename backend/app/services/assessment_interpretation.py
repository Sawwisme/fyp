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

    original = result.get(
        "experimental_severity",
        result.get("severity"),
    )
    result["experimental_severity"] = (
        dict(original) if isinstance(original, dict) else None
    )

    predictions = result.get("predictions")
    decisions = {}
    unsupported = []
    seen = set()
    valid = isinstance(predictions, list)

    if valid:
        for item in predictions:
            if not isinstance(item, dict):
                valid = False
                break

            condition = item.get("condition")

            if condition not in CONDITIONS or condition in seen:
                valid = False
                break

            seen.add(condition)
            assessed = item.get("assessed", True)

            if type(assessed) is not bool:
                valid = False
                break

            positive = item.get("positive")

            if assessed:
                if type(positive) is not bool:
                    valid = False
                    break

                decisions[condition] = positive
            else:
                if positive is not None:
                    valid = False
                    break

                unsupported.append(condition)

    valid = (
        valid
        and seen == CONDITIONS
        and "healthy" in decisions
    )

    diseases = []
    label = "Unavailable"

    if not valid:
        status = "unavailable"
        reason = (
            "The prediction decisions are incomplete or invalid."
        )

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
                "Healthy and supported disease predictions both "
                "passed their thresholds. No overall severity "
                "is assigned."
            )

        elif not healthy and not diseases:
            status = "inconclusive"
            label = "Inconclusive"
            reason = (
                "No supported classification passed its threshold. "
                "This does not establish a healthy condition."
            )

        elif healthy:
            status = "healthy_pattern"
            label = "None"
            reason = (
                "No supported disease flags were detected. "
                "This screening result does not confirm health "
                "or exclude conditions outside its coverage."
            )

        else:
            status = "disease_flags"
            estimate = (
                original if isinstance(original, dict) else {}
            )

            scored_conditions = estimate.get("scored_conditions")

            scope_matches = (
                estimate.get("calculation_version")
                == "supported-conditions-v1"
                and isinstance(scored_conditions, list)
                and all(
                    isinstance(condition, str)
                    for condition in scored_conditions
                )
                and sorted(scored_conditions) == diseases
            )

            if unsupported and not scope_matches:
                # The existing severity calculation may include
                # unsupported conditions or their segmentation area.
                # Withhold it until that calculation is updated.
                label = "Unavailable"
                reason = (
                    "Supported disease classifications passed "
                    "their thresholds. Overall severity is not "
                    "assigned because the existing estimate has "
                    "not been restricted to supported conditions."
                )
            else:
                label = estimate.get("label", "Unavailable")

                if label not in {"Mild", "Moderate", "Severe"}:
                    label = "Unavailable"

                reason = (
                    estimate.get("reason")
                    or "Disease classifications passed their thresholds."
                )

    unsupported = sorted(unsupported)

    result["decision"] = {
        "version": "screening-decision-v2",
        "status": status,
        "disease_flags": diseases,
        "not_assessed_conditions": unsupported,
        "reason": reason,
    }

    result["coverage"] = {
        "partial": bool(unsupported),
        "not_assessed_conditions": unsupported,
        "note": (
            "Some conditions are not assessed for this species."
            if unsupported
            else None
        ),
    }

    result["severity"] = {
        "label": label,
        "method": (
            "experimental_rule_based"
            if status == "disease_flags"
            and label in {"Mild", "Moderate", "Severe"}
            else "not_assigned"
        ),
        "reason": reason,
    }

    return result