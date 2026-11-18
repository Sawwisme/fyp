from fastapi import HTTPException


def select_checkout_items(items, selected_product_ids):
    items = list(items)

    if selected_product_ids is None:
        return items

    requested = set(selected_product_ids)
    available = {item.product_id for item in items}

    if not requested or not requested.issubset(available):
        raise HTTPException(
            status_code=409,
            detail=(
                "Some selected products are no longer in this "
                "clinic's cart. Return to the cart and review it."
            ),
        )

    return [
        item
        for item in items
        if item.product_id in requested
    ]