"""Species coverage of the dental classifier's labelled dataset."""

SUPPORTED_DISEASES = {
    "cat": {"plaque", "gingivitis"},
    "dog": {"gingivitis", "calculus"},
}

SPECIES_ALIASES = {
    "cat": "cat",
    "feline": "cat",
    "dog": "dog",
    "canine": "dog",
}


def apply_species_policy(predictions, species):
    """
    predictions: dictionary keyed by condition, with confidence,
                 threshold and positive fields.

    Returns new dictionaries; original model outputs stay unchanged.
    """
    species = SPECIES_ALIASES.get(str(species or "").strip().lower())
    supported = SUPPORTED_DISEASES.get(species, set())

    output = {}

    for condition, prediction in predictions.items():
        item = dict(prediction)
        item["raw_positive"] = prediction.get("positive")

        # Healthy classification is available only for supported species.
        assessed = species is not None and (
            condition == "healthy" or condition in supported
        )

        item["assessed"] = assessed

        if assessed:
            item["positive"] = prediction["positive"]
            item["assessment_note"] = None
        else:
            item["positive"] = None
            item["assessment_note"] = (
                "Not assessed for this species."
                if species is not None
                else "Pet species is required for interpretation."
            )

        output[condition] = item

    return output