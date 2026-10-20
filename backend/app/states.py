MALAYSIAN_STATES = {
    "Johor": ["Johor"],
    "Kedah": ["Kedah"],
    "Kelantan": ["Kelantan"],
    "Melaka": ["Melaka", "Malacca"],
    "Negeri Sembilan": ["Negeri Sembilan"],
    "Pahang": ["Pahang"],
    "Pulau Pinang": ["Pulau Pinang", "Penang"],
    "Perak": ["Perak"],
    "Perlis": ["Perlis"],
    "Sabah": ["Sabah"],
    "Sarawak": ["Sarawak"],
    "Selangor": ["Selangor"],
    "Terengganu": ["Terengganu"],
    "W.P. Kuala Lumpur": [
        "Kuala Lumpur",
        "Wilayah Persekutuan Kuala Lumpur",
        "Federal Territory of Kuala Lumpur",
    ],
    "W.P. Labuan": [
        "Labuan",
        "Wilayah Persekutuan Labuan",
        "Federal Territory of Labuan",
    ],
    "W.P. Putrajaya": [
        "Putrajaya",
        "Wilayah Persekutuan Putrajaya",
        "Federal Territory of Putrajaya",
    ],
}


def matches_selected_state(properties: dict, state_name: str) -> bool:
    def normalize(value):
        return "".join(
            character
            for character in str(value).casefold()
            if character.isalnum()
        )

    aliases = {
        normalize(alias)
        for alias in MALAYSIAN_STATES[state_name]
    }

    state = properties.get("state")

    if state:
        return normalize(state) in aliases

    # Some federal-territory records use city/county instead.
    return any(
        normalize(properties.get(field, "")) in aliases
        for field in ("city", "county", "district")
    )