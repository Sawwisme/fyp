from sqlalchemy import case, func, or_, select
from datetime import date, datetime, timedelta, timezone
import re
from decimal import Decimal
from app.schemas.chatbot import ProductSearchPreferences
from app.models import Clinic, Product, ProductCategory
from app.services.chatbot_context_service import build_chat_context
from app.services.product_recommendation_rules import (
    build_product_match,
)

from app.services.chatbot_language_service import (
    render_product_match_reason,
    render_product_search_reply,
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

def parse_record_time(value):
    if not isinstance(value, str):
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def consultation_covers_analysis(consultation, analysis):
    if not consultation or not analysis:
        return False

    if (
        consultation.get("ai_analysis_id") is None
        or consultation["ai_analysis_id"]
        != analysis.get("analysis_id")
    ):
        return False

    # Keep an outstanding clinic-review requirement active.
    if consultation.get("in_clinic_review_required"):
        return False

    consultation_time = parse_record_time(
        consultation.get("consultation_date")
    )
    analysis_time = parse_record_time(
        analysis.get("analysis_date")
    )

    return (
        consultation_time is not None
        and analysis_time is not None
        and consultation_time >= analysis_time
    )

def product_reply(
    db,
    current_user,
    pet_id,
    *,
    products=None,
    request_text="",
    language="en",
    product_preferences=None,
):
    def text(en, ms, zh):
        return {"en": en, "ms": ms, "zh": zh}.get(language, en)

    # Checks owner access and selected-pet ownership.
    context = build_chat_context(db, current_user, pet_id)

    pet = context.get("pet")

    if pet is None:
        return (
            text(
                "Start a pet-linked chat to filter products by recorded "
                "species and age. You can still browse clinic catalogues "
                "in Shop.",
                "Pilih haiwan peliharaan untuk menapis produk mengikut "
                "spesies dan umur yang direkodkan. Anda masih boleh "
                "melayari katalog klinik di Kedai.",
                "请选择聊天关联的宠物，以便根据已记录的物种和年龄筛选产品。"
                "您仍可在商城浏览诊所的产品目录。",
            ),
            "OPEN_SHOP",
        )

    species = (pet.get("species") or "").strip().lower()

    species = {
        "feline": "cat",
        "canine": "dog",
    }.get(species, species)

    if species not in {"cat", "dog"}:
        return (
            text(
                "Product matching currently supports cats and dogs. "
                "Check your pet profile or ask your clinic about "
                "suitable products.",
                "Padanan produk kini menyokong kucing dan anjing. "
                "Semak profil haiwan anda atau hubungi klinik untuk "
                "bertanya tentang produk yang sesuai.",
                "产品匹配目前支持猫和狗。请检查宠物资料，"
                "或向诊所咨询适合的产品。",
            ),
            "OPEN_SHOP",
        )

    age_months = pet_age_months(pet)

    latest = context.get("latest_analysis")
    review_note = None

    consultation = context.get("latest_consultation")

    covered_by_consultation = consultation_covers_analysis(
        consultation,
        latest,
    )

    reviews = [
        review
        for review in context.get("vet_reviews", [])
        if latest is not None
        and review["analysis_id"] == latest["analysis_id"]
    ]

    if covered_by_consultation:
        consultation_time = parse_record_time(
            consultation.get("consultation_date")
        )

        remaining_reviews = []

        for review in reviews:
            review_time = parse_record_time(
                review.get("reviewed_at")
            )

            superseded = (
                review.get("clinic_id")
                == consultation.get("clinic_id")
                and review_time is not None
                and review_time <= consultation_time
            )

            if not superseded:
                remaining_reviews.append(review)

        reviews = remaining_reviews

        consultation_id = consultation["consultation_id"]

        review_note = text(
            f"Using consultation #{consultation_id}, "
            "which is linked to this assessment. "
            "Product suggestions follow its recorded "
            "diagnosis and care instructions.",
            f"Menggunakan konsultasi #{consultation_id} "
            "yang dipautkan kepada penilaian ini. "
            "Cadangan produk berdasarkan diagnosis dan "
            "arahan penjagaan yang direkodkan.",
            f"正在使用与本次评估关联的问诊记录 #{consultation_id}。"
            "产品建议依据该记录中的诊断和护理指示。",
        )

    if len(reviews) > 1:
        return (
            text(
                "There are multiple clinic reviews for this assessment. "
                "Read their recorded recommendations before choosing "
                "products. Contact the reviewing clinics if their "
                "instructions differ.",
                "Penilaian ini mempunyai beberapa ulasan klinik. "
                "Baca cadangan yang direkodkan sebelum memilih produk. "
                "Jika arahannya berbeza, hubungi klinik yang memberikan "
                "ulasan untuk mendapatkan penjelasan.",
                "这项评估有多份诊所审核记录。选择产品前，"
                "请先阅读已记录的建议。如果指示不同，"
                "请联系审核诊所确认。",
            ),
            "OPEN_AI_ANALYSIS",
        )

    if reviews:
        review = reviews[0]
        action = review.get("recommended_action")

        heading = text(
            f"Recorded vet review #{review['review_id']} "
            f"(clinic #{review['clinic_id']}): ",
            f"Ulasan veterinar direkodkan #{review['review_id']} "
            f"(klinik #{review['clinic_id']}): ",
            f"已记录的兽医审核 #{review['review_id']} "
            f"（诊所 #{review['clinic_id']}）：",
        )

        # Preserve the actual veterinary feedback.
        recorded_feedback = review.get("feedback")
        feedback = heading + (
            recorded_feedback
            if recorded_feedback
            else text(
                "No feedback recorded.",
                "Tiada maklum balas direkodkan.",
                "未记录审核意见。",
            )
        )

        if action == "home_care":
            review_note = feedback + "\n" + text(
                "The catalogue below does not establish that "
                "a particular product was endorsed by this vet.",
                "Katalog di bawah tidak bermaksud bahawa produk "
                "tertentu telah disyorkan oleh veterinar ini.",
                "下方产品目录并不代表这位兽医认可或推荐了某个具体产品。",
            )
        else:
            # Keep the recorded action value unchanged.
            recorded_action = (
                str(action)
                if action
                else text(
                    "Not recorded",
                    "Tidak direkodkan",
                    "未记录",
                )
            )

            return (
                feedback
                + "\n"
                + text(
                    f"Recorded recommendation: {recorded_action}. ",
                    f"Cadangan direkodkan: {recorded_action}. ",
                    f"已记录的建议：{recorded_action}。",
                )
                + text(
                    "Check your existing appointments and contact "
                    "the clinic about the next step. Products should "
                    "not replace the recommended assessment.",
                    "Semak janji temu sedia ada dan hubungi klinik "
                    "tentang langkah seterusnya. Produk tidak boleh "
                    "menggantikan pemeriksaan yang disyorkan.",
                    "请查看已有预约，并联系诊所确认下一步。"
                    "产品不能代替建议进行的检查。",
                ),
                "OPEN_APPOINTMENTS",
            )

    elif (
        latest is not None
        and latest.get("estimated_severity") == "severe"
        and not covered_by_consultation
    ):
        return (
            text(
                "The latest AI assessment has Estimated Severity: "
                "Severe, with no completed vet review recorded for "
                "this assessment. Prioritize veterinary assessment "
                "rather than choosing products as treatment. "
                "Check existing appointments before booking another. "
                "The AI estimate is not a confirmed diagnosis.",
                "Penilaian AI terkini mempunyai anggaran tahap "
                "keterukan: Teruk. Tiada ulasan veterinar yang telah "
                "selesai direkodkan untuk penilaian ini. Utamakan "
                "pemeriksaan veterinar dan jangan gunakan produk "
                "sebagai pengganti pemeriksaan tersebut. Semak "
                "janji temu sedia ada sebelum membuat tempahan lain. "
                "Anggaran AI ini bukan diagnosis yang disahkan.",
                "最近的 AI 评估显示估计严重程度为“严重”，"
                "但尚无针对这项评估的已完成兽医审核记录。"
                "请优先安排兽医检查，不要用购买产品代替检查。"
                "再次预约前，请先查看已有预约。"
                "AI 的估计并非确诊结果。",
            ),
            "OPEN_APPOINTMENTS",
        )

    preferences = ProductSearchPreferences.model_validate(
        product_preferences or {}
    )

    request_filters, requested_categories, budget = (
        product_request_filters(request_text)
    )

    if preferences.clinic_id is not None:
        request_filters.append(
            Clinic.clinic_id == preferences.clinic_id
        )

    if preferences.state is not None:
        request_filters.append(
            Clinic.state == preferences.state
        )

    if preferences.fulfilment == "pickup":
        request_filters.append(
            Clinic.shop_pickup_enabled.is_(True)
        )
    elif preferences.fulfilment == "delivery":
        request_filters.append(
            Clinic.shop_delivery_enabled.is_(True)
        )

    care_context = build_product_match(context, request_text)
    care_tags = care_context["tags"]

    if care_context["blocked_reason"]:
        original_reason = care_context["blocked_reason"]

        restriction_message = (
            "Your consultation contains a restriction, "
            "uncertainty, or a condition requiring more "
            "individual guidance. I have not automatically "
            "selected care products. Follow the recorded "
            "instructions and contact your clinic if needed."
        )

        # Translate only this known message.
        # Preserve any other safety explanation unchanged.
        if original_reason == restriction_message:
            reply = text(
                original_reason,
                "Rekod konsultasi anda mengandungi sekatan, "
                "ketidakpastian atau keadaan yang memerlukan "
                "panduan khusus. Saya tidak memilih produk "
                "penjagaan secara automatik. Ikuti arahan "
                "yang direkodkan dan hubungi klinik anda "
                "jika memerlukan penjelasan.",
                "您的问诊记录包含使用限制、不确定情况，"
                "或需要个别指导的状况。因此没有自动选择护理产品。"
                "请遵循已记录的指示，如有需要，请联系诊所确认。",
            )
        else:
            reply = original_reason

        return reply, "OPEN_MEDICAL_HISTORY"

    request_filters.append(
        Product.recommendation_enabled == 1
    )

    if not care_tags:
        if context.get("latest_consultation"):
            return (
                text(
                    "I could not match the latest consultation "
                    "to a supported product-care purpose. "
                    "I have not selected unrelated products. "
                    "You can still browse the clinic shop.",
                    "Saya tidak dapat memadankan konsultasi terkini "
                    "dengan tujuan penjagaan produk yang disokong. "
                    "Saya tidak memilih produk yang tidak berkaitan. "
                    "Anda masih boleh melayari kedai klinik.",
                    "我无法将最近的问诊记录匹配到系统支持的产品护理用途。"
                    "因此没有选择不相关的产品。您仍可浏览诊所商城。",
                ),
                "OPEN_SHOP",
            )

        return (
            text(
                "What would you like help with: routine brushing, "
                "plaque control, or breath care? "
                "You can include a product type and budget.",
                "Apakah tujuan penjagaan anda: memberus gigi secara "
                "rutin, kawalan plak atau penjagaan nafas? "
                "Anda boleh nyatakan jenis produk dan bajet.",
                "您需要哪方面的护理产品：日常刷牙、牙菌斑控制，"
                "还是口气护理？您也可以说明产品类型和预算。",
            ),
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
            Clinic.state.label("clinic_state"),
            Clinic.shop_pickup_enabled,
            Clinic.shop_delivery_enabled,
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
        translated_reply = render_product_search_reply(
            language=language,
            no_match=True,
        )

        return (
            translated_reply or (
                "No available products match the requested product type, "
                "budget, and this pet's recorded species/age criteria. "
                "Try another product type or budget, "
                "or browse the clinic shops."
            ),
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

            translated_reason = render_product_match_reason(
                species=species,
                age_months=age_months,
                minimum_age_months=product["minimum_age_months"],
                category_name=product["category_name"],
                category_requested=bool(requested_categories),
                budget=budget,
                matched_tags=matched_tags,
                source=care_context["source"],
                language=language,
            )

            if translated_reason is not None:
                reason = translated_reason

            products.append({
                "product_id": product["product_id"],
                "clinic_id": product["clinic_id"],
                "product_name": product["product_name"],
                "clinic_name": product["clinic_name"],
                "price": str(product["price"]),
                "category_name": product["category_name"],
                "recommendation_reason": reason,
                "suitability_notes": product["suitability_notes"],
                "clinic_state": product["clinic_state"],
                "shop_pickup_enabled":
                    product["shop_pickup_enabled"],
                "shop_delivery_enabled":
                    product["shop_delivery_enabled"],
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

    translated_reply = render_product_search_reply(
        language=language,
        pet_name=pet["name"],
        count=len(records),
        source=care_context["source"],
        categories=requested_categories,
        budget=budget,
        review_note=review_note,
        explanation=care_context["explanation"],
    )

    return (
        translated_reply
        if translated_reply is not None
        else "\n\n".join(sections),
        "OPEN_SHOP",
    )