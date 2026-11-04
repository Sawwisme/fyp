from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    OrderItem,
    Product,
    ProductStockMovement,
    Refund,
    Transaction,
)
from app.schemas.clinic_refunds import RefundStockReview
from app.services.clinic_refund_service import _get_clinic_order
from app.services.shop_refund_service import build_refund_response


def review_refund_stock(
    db: Session,
    current_user,
    order_id: int,
    refund_id: int,
    data: RefundStockReview,
):
    try:
        _, order = _get_clinic_order(
            db, current_user, order_id
        )

        refund = db.scalar(
            select(Refund)
            .join(
                Transaction,
                Transaction.transaction_id
                == Refund.transaction_id,
            )
            .where(
                Refund.refund_id == refund_id,
                Transaction.order_id == order.order_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )

        if refund is None:
            raise HTTPException(404, "Refund request not found.")

        if (
            refund.status != "succeeded"
            or order.order_status != "refunded"
        ):
            raise HTTPException(
                409,
                "Stock can be reviewed after the refund succeeds.",
            )

        if refund.stock_reviewed_at is not None:
            raise HTTPException(
                409,
                "The stock decision has already been recorded. "
                "Reload to view it.",
            )

        if refund.version != data.expected_version:
            raise HTTPException(
                409,
                "This refund changed. Reload before continuing.",
            )

        order_items = db.scalars(
            select(OrderItem)
            .where(OrderItem.order_id == order.order_id)
            .order_by(OrderItem.product_id)
            .with_for_update()
        ).all()

        ordered_quantities = {}

        for item in order_items:
            ordered_quantities[item.product_id] = (
                ordered_quantities.get(item.product_id, 0)
                + item.quantity
            )

        movements = db.scalars(
            select(ProductStockMovement)
            .where(
                ProductStockMovement.reference_order_id
                == order.order_id,
            )
            .with_for_update()
        ).all()

        already_released = (
            order.stock_released_at is not None
            or any(
                movement.movement_type == "order_released"
                for movement in movements
            )
        )

        if data.items and already_released:
            raise HTTPException(
                409,
                "This order's reserved stock was already restored. "
                "Do not restock it again.",
            )

        if any(
            movement.movement_type == "refund_return"
            for movement in movements
        ):
            raise HTTPException(
                409,
                "Returned stock movements already exist. "
                "The stock record needs reconciliation.",
            )

        reserved_quantities = {}

        for movement in movements:
            if movement.movement_type == "order_reserved":
                reserved_quantities[movement.product_id] = (
                    reserved_quantities.get(movement.product_id, 0)
                    - movement.quantity_change
                )

        for item in data.items:
            ordered = ordered_quantities.get(item.product_id)

            if (
                ordered is None
                or ordered <= 0
                or item.quantity > ordered
                or reserved_quantities.get(item.product_id) != ordered
            ):
                raise HTTPException(
                    422,
                    "A return quantity does not match the "
                    "original order and stock reservation.",
                )

        products = {}

        if data.items:
            products = {
                product.product_id: product
                for product in db.scalars(
                    select(Product)
                    .where(
                        Product.product_id.in_([
                            item.product_id
                            for item in data.items
                        ]),
                        Product.clinic_id == order.clinic_id,
                    )
                    .order_by(Product.product_id)
                    .execution_options(populate_existing=True)
                    .with_for_update()
                ).all()
            }

        # Validate every product before changing any stock.
        for item in data.items:
            product = products.get(item.product_id)

            if product is None:
                raise HTTPException(
                    409,
                    "A returned product is unavailable in this clinic.",
                )

            if (
                product.stock_quantity < 0
                or product.stock_quantity + item.quantity > 1000000
            ):
                raise HTTPException(
                    409,
                    "The return would exceed the stock limit.",
                )

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        for item in data.items:
            product = products[item.product_id]
            before = product.stock_quantity

            product.stock_quantity += item.quantity
            product.version += 1
            product.updated_at = now

            db.add(
                ProductStockMovement(
                    product_id=product.product_id,
                    created_by_user_id=current_user.user_id,
                    quantity_change=item.quantity,
                    quantity_before=before,
                    quantity_after=product.stock_quantity,
                    reason=(
                        f"Refund #{refund.refund_id}: "
                        f"{data.notes}"
                    )[:1000],
                    movement_type="refund_return",
                    reference_order_id=order.order_id,
                    created_at=now,
                )
            )

        refund.stock_reviewed_at = now
        refund.stock_reviewed_by = current_user.user_id
        refund.stock_review_notes = data.notes
        refund.stock_return_items = [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
            }
            for item in sorted(
                data.items,
                key=lambda item: item.product_id,
            )
        ]
        refund.version += 1

        db.flush()

        result = build_refund_response(
            refund, order.order_id
        )

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise