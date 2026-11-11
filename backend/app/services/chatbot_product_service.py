from sqlalchemy import or_, select
from datetime import date, datetime, timedelta, timezone

from app.models import Clinic, Product, ProductCategory
from app.services.chatbot_context_service import build_chat_context

def pet_age_months(pet):
    value = pet.get("date_of_birth")

    if not isinstance(value, str):
        return None

    try:
        born = date.fromisoformat(value)
    except ValueError:
        return None

    today = datetime.now(
        timezone(timedelta(hours=8))
    ).date()

    if born > today:
        return None

    return (
        (today.year - born.year) * 12
        + today.month
        - born.month
        - int(today.day < born.day)
    )

def product_reply(db, current_user, pet_id):
    # Checks owner access and selected-pet ownership.
    context = build_chat_context(db, current_user, pet_id)

    pet = context.get("pet")

    if pet is None:
        return (
            "Start a pet-linked chat to filter products by "
            "recorded species and age. You can still browse "
            "clinic catalogues in Shop.",
            "OPEN_SHOP",
        )

    species = (pet.get("species") or "").strip().lower()

    species = {
        "feline": "cat",
        "canine": "dog",
    }.get(species, species)

    if species not in {"cat", "dog"}:
        return (
            "Product matching currently supports cats and dogs. "
            "Check your pet profile or ask your clinic "
            "about suitable products.",
            "OPEN_SHOP",
        )

    age_months = pet_age_months(pet)

    latest = context.get("latest_analysis")
    review_note = None

    reviews = [
        review
        for review in context.get("vet_reviews", [])
        if latest is not None
        and review["analysis_id"] == latest["analysis_id"]
    ]

    if len(reviews) > 1:
        return (
            "There are multiple clinic reviews for this assessment. "
            "Read their recorded recommendations before choosing "
            "products. Contact the reviewing clinics if their "
            "instructions differ.",
            "OPEN_AI_ANALYSIS",
        )

    if reviews:
        review = reviews[0]
        action = review.get("recommended_action")

        feedback = (
            f"Recorded vet review #{review['review_id']} "
            f"(clinic #{review['clinic_id']}): "
            f"{review.get('feedback') or 'No feedback recorded.'}"
        )

        if action == "home_care":
            review_note = (
                feedback
                + "\nThe catalogue below does not establish that "
                "a particular product was endorsed by this vet."
            )
        else:
            return (
                feedback
                + "\nThe recorded recommendation is: "
                + (
                    action.replace("_", " ")
                    if action
                    else "contact the reviewing clinic"
                )
                + ". Check your existing appointments and contact "
                "the clinic about the next step. Products should "
                "not replace the recommended assessment.",
                "OPEN_APPOINTMENTS",
            )

    elif (
        latest is not None
        and latest.get("estimated_severity") == "severe"
    ):
        return (
            "The latest AI assessment has Estimated Severity: "
            "Severe, with no completed vet review recorded for "
            "this assessment. Prioritize veterinary assessment "
            "rather than choosing products as treatment. "
            "Check existing appointments before booking another. "
            "The AI estimate is not a confirmed diagnosis.",
            "OPEN_APPOINTMENTS",
        )
    
    records = db.execute(
        select(
            Product.product_id,
            Product.product_name,
            Product.price,
            ProductCategory.category_name,
            Clinic.clinic_name,
            Product.target_species,
            Product.minimum_age_months,
            Product.suitability_notes,
        )
        .join(
            ProductCategory,
            ProductCategory.category_id == Product.category_id,
        )
        .join(
            Clinic,
            Clinic.clinic_id == Product.clinic_id,
        )
        .where(
            Product.status == "active",
            Product.stock_quantity > 0,
            Clinic.status == "active",
            or_(
                Clinic.shop_pickup_enabled.is_(True),
                Clinic.shop_delivery_enabled.is_(True),
            ),
            or_(
                ProductCategory.clinic_id.is_(None),
                ProductCategory.clinic_id == Product.clinic_id,
            ),
            Product.target_species.in_([species, "both"]),
            Product.minimum_age_months.is_not(None),
            (
                Product.minimum_age_months <= age_months
                if age_months is not None
                else Product.minimum_age_months == 0
            ),
        )
        .order_by(
            Clinic.clinic_name,
            Product.product_name,
            Product.product_id,
        )
        .limit(6)
    ).mappings().all()

    if not records:
        return (
            "I found no in-stock products with recorded species "
            "and minimum-age information matching this pet. "
            "Some products may have incomplete suitability details. "
            "Browse Shop or ask the clinic before choosing.",
            "OPEN_SHOP",
        )
    
    sections = [
        f"Catalogue options matching {pet['name']}'s recorded "
        "species and minimum-age criteria. This does not establish "
        "medical suitability or a treatment recommendation:"
    ]

    if review_note:
        sections.insert(0, review_note)

    for product in records:
        sections.append(
            f"• {product['product_name']}\n"
            f"Category: {product['category_name']}\n"
            f"Clinic: {product['clinic_name']}\n"
            f"Price: RM {product['price']:.2f}"
            f"\nLabelled species: {product['target_species']}"
            f"\nMinimum age: {product['minimum_age_months']} months"
            f"\nLabel notes: "
            f"{product['suitability_notes'] or 'Not recorded'}"
        )

    sections.append(
        "Matching uses clinic-recorded product information. "
        "Read all label restrictions and ask your vet about "
        "medical suitability. Products do not replace treatment. "
        "Open Shop to select the clinic and view full details."
    )

    return "\n\n".join(sections), "OPEN_SHOP"