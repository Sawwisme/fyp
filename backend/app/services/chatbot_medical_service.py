from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.services.owner_medical_history_service import list_medical_history
from app.services.pet_service import get_owner_profile, get_pet


MALAYSIA_TIME = timezone(timedelta(hours=8))

# Translate presentation text only. Database values stay unchanged.
TEXT = {
    "select_pet": (
        "Select a pet for this chat to view its medical records.",
        "Pilih haiwan untuk perbualan ini bagi melihat rekod perubatannya.",
        "请先为此对话选择宠物，以查看其医疗记录。",
    ),
    "missing": ("Not recorded", "Tidak direkodkan", "未记录"),
    "date": ("Date", "Tarikh", "日期"),
    "clinic": ("Clinic", "Klinik", "诊所"),
    "vet": ("Veterinarian", "Doktor veterinar", "兽医"),
    "consultation": ("Consultation", "Konsultasi", "诊疗记录"),
    "diagnosis": ("Recorded diagnosis", "Diagnosis direkodkan", "已记录的诊断"),
    "history_heading": (
        "Up to three recent completed consultations for {pet}:",
        "Sehingga tiga konsultasi terkini yang selesai untuk {pet}:",
        "{pet} 最近已完成的诊疗记录（最多显示三次）：",
    ),
    "no_history": (
        "No completed consultation records are available for {pet}. "
        "AI assessments are stored separately.",
        "Tiada rekod konsultasi selesai tersedia untuk {pet}. "
        "Penilaian AI disimpan secara berasingan.",
        "目前没有可查看的 {pet} 已完成诊疗记录。AI 评估单独保存。",
    ),
    "treatments": (
        "Treatments — up to three shown",
        "Rawatan — sehingga tiga dipaparkan",
        "治疗项目（最多显示三项）",
    ),
    "no_treatments": (
        "No treatments recorded in this consultation.",
        "Tiada rawatan direkodkan dalam konsultasi ini.",
        "本次诊疗未记录治疗项目。",
    ),
    "prescription_count": (
        "Prescriptions recorded",
        "Preskripsi direkodkan",
        "已记录的处方数量",
    ),
    "history_note": (
        "These are saved veterinary records, not a new diagnosis. "
        "Open Medical History for complete details. "
        "Clinical entries are shown in their original language.",
        "Ini ialah rekod veterinar yang disimpan, bukan diagnosis baharu. "
        "Buka Sejarah Perubatan untuk butiran lengkap. "
        "Catatan klinikal dipaparkan dalam bahasa asal.",
        "以上为已保存的兽医记录，并非新的诊断。"
        "请打开医疗历史查看完整详情。临床内容保留原文。",
    ),
    "latest": (
        "{pet}'s latest completed consultation",
        "Konsultasi selesai terkini untuk {pet}",
        "{pet} 最近一次已完成的诊疗",
    ),
    "no_prescriptions": (
        "No prescriptions are recorded in this consultation. "
        "Older visits may have prescriptions; check Medical History.",
        "Tiada preskripsi direkodkan dalam konsultasi ini. "
        "Lawatan terdahulu mungkin mempunyai preskripsi; semak Sejarah Perubatan.",
        "本次诊疗未记录处方。较早的就诊可能有处方，请查看医疗历史。",
    ),
    "prescription_heading": (
        "Saved prescription instructions — up to five shown. "
        "These are historical records, not confirmation that medicines "
        "should still be taken. Clinical fields are copied in their original language.",
        "Arahan preskripsi tersimpan — sehingga lima dipaparkan. "
        "Ini ialah rekod terdahulu, bukan pengesahan bahawa ubat masih perlu diberikan. "
        "Maklumat klinikal disalin dalam bahasa asal.",
        "已保存的处方说明（最多显示五项）。"
        "这些是历史记录，不代表目前仍应使用这些药物。临床字段保留原文。",
    ),
    "prescription": ("Prescription", "Preskripsi", "处方"),
    "medicine": ("Medicine", "Ubat", "药物"),
    "prescription_date": ("Prescription date", "Tarikh preskripsi", "处方日期"),
    "dosage": ("Recorded dosage", "Dos direkodkan", "已记录的剂量"),
    "route": ("Route", "Cara pemberian", "给药途径"),
    "frequency": ("Frequency", "Kekerapan", "用药频率"),
    "duration": ("Duration", "Tempoh", "用药时长"),
    "instructions": ("Instructions", "Arahan", "用药说明"),
    "prescription_note": (
        "The chatbot copies these fields without calculating or changing them. "
        "Do not restart or change medication based on an old record. "
        "Contact the prescribing clinic if instructions are unclear.",
        "Chatbot menyalin maklumat ini tanpa mengira atau mengubahnya. "
        "Jangan mulakan semula atau ubah ubat berdasarkan rekod lama. "
        "Hubungi klinik yang mengeluarkan preskripsi jika arahan tidak jelas.",
        "聊天机器人仅复制这些字段，不计算或修改剂量。"
        "请勿根据旧记录重新开始用药或调整药物。"
        "如说明不清楚，请联系开具处方的诊所。",
    ),
}


def translated(key, language="en", **values):
    index = {"en": 0, "ms": 1, "zh": 2}.get(language, 0)
    return TEXT[key][index].format(**values)


def recorded(value, language):
    return (
        translated("missing", language)
        if value is None or value == ""
        else str(value)
    )


def visit_date(value, language="en"):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(MALAYSIA_TIME).strftime(
            "%Y-%m-%d %H:%M MYT"
        )
    return recorded(value, language)


def consultation_heading(record, language):
    return "\n".join([
        f"{translated('consultation', language)} "
        f"#{record['consultation_id']}",
        f"{translated('date', language)}: "
        f"{visit_date(record.get('consultation_date'), language)}",
        f"{translated('clinic', language)}: "
        f"{recorded(record.get('clinic_name'), language)}",
        f"{translated('vet', language)}: "
        f"{recorded(record.get('veterinarian_name'), language)}",
    ])


def medical_record_reply(
    db, current_user, pet_id, intent, *, language="en"
):
    if current_user.role != "pet_owner":
        raise HTTPException(403, "A pet owner account is required.")

    get_owner_profile(db, current_user)

    if pet_id is None:
        return translated("select_pet", language)

    # Retain the existing ownership check.
    pet = get_pet(db, current_user, pet_id)

    records = list_medical_history(
        db=db,
        current_user=current_user,
        pet_id=pet.pet_id,
        offset=0,
        limit=3,
    )

    if not records:
        return translated("no_history", language, pet=pet.pet_name)

    if intent == "recorded_prescriptions":
        return prescription_reply(
            pet.pet_name, records[0], language=language
        )

    sections = [
        translated("history_heading", language, pet=pet.pet_name)
    ]

    for record in records[:3]:
        lines = [
            consultation_heading(record, language),
            f"{translated('diagnosis', language)}: "
            f"{recorded(record.get('diagnosis'), language)}",
        ]

        treatments = record.get("treatments") or []

        if treatments:
            lines.append(translated("treatments", language))

            for treatment in treatments[:3]:
                status = (
                    treatment.get("current_status")
                    or treatment.get("recorded_status")
                )
                lines.append(
                    f"• {recorded(treatment.get('treatment_name'), language)}"
                    f" — {recorded(status, language)}"
                )
        else:
            lines.append(translated("no_treatments", language))

        lines.append(
            f"{translated('prescription_count', language)}: "
            f"{len(record.get('prescriptions') or [])}"
        )
        sections.append("\n".join(lines))

    sections.append(translated("history_note", language))
    return "\n\n".join(sections)


def prescription_reply(pet_name, record, *, language="en"):
    sections = [
        translated("latest", language, pet=pet_name),
        consultation_heading(record, language),
    ]

    prescriptions = record.get("prescriptions") or []

    if not prescriptions:
        sections.append(translated("no_prescriptions", language))
        return "\n\n".join(sections)

    sections.append(translated("prescription_heading", language))

    for prescription in prescriptions[:5]:
        # Support ORM records and dictionaries without modifying either.
        def value(field):
            raw = (
                prescription.get(field)
                if isinstance(prescription, dict)
                else getattr(prescription, field, None)
            )
            return recorded(raw, language)

        lines = [
            f"{translated('prescription', language)} "
            f"#{value('prescription_id')}"
        ]

        for label, field in [
            ("medicine", "medication_name"),
            ("prescription_date", "prescription_date"),
            ("dosage", "dosage"),
            ("route", "administration_route"),
            ("frequency", "frequency"),
            ("duration", "duration"),
            ("instructions", "instructions"),
        ]:
            lines.append(
                f"{translated(label, language)}: {value(field)}"
            )

        sections.append("\n".join(lines))

    sections.append(translated("prescription_note", language))
    return "\n\n".join(sections)