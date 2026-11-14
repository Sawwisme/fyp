from sqlalchemy import case, func, or_, select
from datetime import date, datetime, timedelta, timezone
import re
from decimal import Decimal

from app.models import Clinic, Product, ProductCategory
from app.services.chatbot_context_service import build_chat_context
from app.services.product_recommendation_rules import (
    build_product_match,
)

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

def product_request_filters(message):
    text = (message or "").lower().strip()

    category_patterns = {
        "Toothbrushes": r"\b(toothbrush(?:es)?|tooth brush(?:es)?)\b",
        "Pet Toothpaste": r"\b(toothpaste|tooth paste)\b",
        "Dental Chews": r"\b(dental chews?|chews?)\b",
        "Dental Toys": r"\b(dental toys?|toys?)\b",
        "Oral Care Solutions": (
            r"\b(water additives?|oral rinses?|oral sprays?|"
            r"mouthwash|oral care solutions?)\b"
        ),
        "Dental Care Accessories": r"\b(dental accessories)\b",
    }

    categories = [
        category
        for category, pattern in category_patterns.items()
        if re.search(pattern, text)
    ]

    # Examples: "under RM30", "below 25", "budget RM 40".
    budget_match = re.search(
        r"\b(?:under|below|up to|maximum|max|budget)"
        r"\s*(?:of\s*)?(?:rm\s*)?"
        r"(\d+(?:\.\d{1,2})?)(?![\d.])",
        text,
    )

    budget = (
        Decimal(budget_match.group(1))
        if budget_match
        else None
    )

    filters = [Product.price > 0]

    if categories:
        filters.append(
            ProductCategory.category_name.in_(categories)
        )

    if budget is not None:
        filters.append(Product.price <= budget)

    return filters, categories, budget

def product_reply(db, current_user, pet_id, *, products=None,
 request_text="",):
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

    request_filters, requested_categories, budget = (
        product_request_filters(request_text)
    )

    care_context = build_product_match(context, request_text)
    care_tags = care_context["tags"]

    if care_context["blocked_reason"]:
        return (
            care_context["blocked_reason"],
            "OPEN_MEDICAL_HISTORY",
        )

    request_filters.append(
        Product.recommendation_enabled == 1
    )

    if not care_tags:
        if context.get("latest_consultation"):
            return (
                "I could not match the latest consultation "
                "to a supported product-care purpose. "
                "I have not selected unrelated products. "
                "You can still browse the clinic shop.",
                "OPEN_SHOP",
            )

        return (
            "What would you like help with: routine brushing, "
            "plaque control, or breath care? "
            "You can include a product type and budget.",
            None,
        )

    if care_tags:
        request_filters.append(
            or_(*[
                func.json_contains(
                    Product.recommendation_tags,
                    func.json_quote(tag),
                ) == 1
                for tag in sorted(care_tags)
            ])
        )

    consultation = context.get("latest_consultation")

    preferred_clinic_id = (
        consultation["clinic_id"]
        if consultation
        else None
    )
    
    match_score = sum(
        (
            case(
                (
                    func.json_contains(
                        Product.recommendation_tags,
                        func.json_quote(tag),
                    ) == 1,
                    1,
                ),
                else_=0,
            )
            for tag in sorted(care_tags)
        ),
        0,
    )

    records = db.execute(
        select(
            Product.product_id,
            Product.clinic_id,
            Product.product_name,
            Product.price,
            ProductCategory.category_name,
            Clinic.clinic_name,
            Product.target_species,
            Product.minimum_age_months,
            Product.suitability_notes,
            Product.recommendation_tags,
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
            *request_filters,
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
            match_score.desc(),
            case(
                (Product.clinic_id == preferred_clinic_id, 0),
                else_=1,
            ),
            Product.price.asc(),
            Product.product_id.asc(),
        )
        .limit(6)
    ).mappings().all()

    if not records:
        return (
            "No available products match the requested product type, "
            "budget, and this pet's recorded species/age criteria. "
            "Try another product type or budget, or browse the clinic shops.",
            "OPEN_SHOP",
        )

    if products is not None:
        for product in records:
            if age_months is None:
                reason = (
                    f"Listed for {species}s with no minimum-age restriction. "
                    "Your pet's age is not recorded; check the full label."
                )
            else:
                reason = (
                    f"Matches the recorded species ({species}) and age "
                    f"({age_months} months). Minimum product age: "
                    f"{product['minimum_age_months']} months."
                )

            if requested_categories:
                reason += (
                    f" Matches your requested category: "
                    f"{product['category_name']}."
                )

            if budget is not None:
                reason += f" Within your RM {budget:.2f} per-item budget."

            matched_tags = sorted(
                care_tags.intersection(
                    product["recommendation_tags"] or []
                )
            )

            if matched_tags:
                purposes = ", ".join(
                    tag.replace("_", " ")
                    for tag in matched_tags
                )

                reason += (
                    f" Care-purpose match: {purposes}. "
                    f"Source: {care_context['source']}. "
                    "Selected automatically by the chatbot."
                )

            products.append({
                "product_id": product["product_id"],
                "clinic_id": product["clinic_id"],
                "product_name": product["product_name"],
                "clinic_name": product["clinic_name"],
                "price": str(product["price"]),
                "category_name": product["category_name"],
                "recommendation_reason": reason,
                "suitability_notes": product["suitability_notes"],
            })
            
    sections = []

    if review_note:
        sections.append(review_note)

    sections.append(
        f"I found {len(records)} care-product option(s) "
        f"for {pet['name']} using {care_context['source']}."
    )

    if care_context["explanation"]:
        sections.append(care_context["explanation"])

    if requested_categories:
        sections.append(
            "Product type: "
            + ", ".join(requested_categories)
            + "."
        )

    if budget is not None:
        sections.append(
            f"Budget: up to RM {budget:.2f} per item."
        )

    sections.append(
        "The cards below explain each match. "
        "These are automatic home-care suggestions, "
        "not prescriptions or replacements for treatment."
    )

    return "\n\n".join(sections), "OPEN_SHOP"