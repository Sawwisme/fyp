from fastapi import HTTPException

from app.states import MALAYSIAN_STATES


def validate_delivery_destination(clinic, state):
    if state not in MALAYSIAN_STATES:
        raise HTTPException(
            422,
            "Select a valid delivery destination state.",
        )

    coverage = clinic.shop_delivery_states

    if not isinstance(coverage, list) or not coverage:
        raise HTTPException(
            409,
            "This clinic has not configured delivery coverage. "
            "Choose clinic pickup if available.",
        )

    if state not in coverage:
        raise HTTPException(
            422,
            "This clinic does not deliver to the selected state. "
            "Choose another clinic or clinic pickup.",
        )