"""Structured Malay/Chinese assessment text. No database or action execution."""

SUPPORTED_INTENTS = {
    "explain_latest_analysis", "explain_pet_severity", "pet_next_steps",
}

# Each pair is (Bahasa Melayu, Chinese). Record values are interpolated,
# never translated or used as instructions to a model.
TEXT = {
    "select_pet": (
        "Pilih haiwan untuk perbualan ini dahulu supaya rekod yang betul digunakan.",
        "请先为此对话选择宠物，以便查看正确的记录。",
    ),
    "missing": (
        "Tiada penilaian AI lengkap yang anda muat naik untuk {name}. Buka AI Scan untuk menghantar gambar. Jika anda bimbang tentang keadaan haiwan, hubungi doktor veterinar tanpa menunggu imbasan.",
        "没有找到您为{name}上传并完成的AI评估。可打开 AI Scan 上传照片。如果担心宠物的情况，请联系兽医，不必等待扫描。",
    ),
    "heading": (
        "Penilaian AI terkini untuk {name} ({date}) — #{analysis_id}",
        "{name}的最新AI评估（{date}）— #{analysis_id}",
    ),
    "date_missing": ("tarikh tidak tersedia", "日期不可用"),
    "inconclusive": (
        "Keputusan tidak konklusif. Tiada keterukan keseluruhan diberikan. Keputusan ini tidak mengesahkan penyakit atau kesihatan.",
        "结果不确定，未分配总体严重程度。这不能确认患病或健康。",
    ),
    "unavailable": (
        "Tafsiran penilaian tidak tersedia. Jangan meneka rawatan daripada skor mentah.",
        "评估解读不可用。请勿根据原始分数猜测需要何种治疗。",
    ),
    "healthy_pattern": (
        "Tiada tanda penyakit yang disokong melepasi ambang model. Ini tidak menolak masalah pergigian atau keadaan di luar liputan model.",
        "没有受支持的疾病标记超过模型阈值。这不能排除牙齿问题或模型覆盖范围之外的情况。",
    ),
    "flags": (
        "Tanda model: {conditions}. Anggaran keterukan eksperimen: {severity}.",
        "模型标记：{conditions}。实验性严重程度估计：{severity}。",
    ),
    "no_flags": ("tiada tanda penyakit yang disokong", "无受支持的疾病标记"),
    "coverage": (
        "Tidak dinilai oleh pengelas untuk spesies ini: {conditions}. Tidak dinilai bukan bermaksud tiada penyakit.",
        "分类器未评估此物种的以下情况：{conditions}。未评估不代表不存在。",
    ),
    "reference": (
        "Ini ialah rujukan saringan AI, bukan diagnosis yang disahkan atau ukuran keterukan klinikal.",
        "这是AI筛查参考，并非确诊或临床严重程度测量。",
    ),
    "review": (
        "Semakan veterinar #{review_id} — klinik #{clinic_id}\nMaklum balas asal: {feedback}\nNilai keterukan direkodkan: {severity}\nTindakan direkodkan: {action}",
        "兽医审核 #{review_id} — 诊所 #{clinic_id}\n原始反馈：{feedback}\n记录的严重程度：{severity}\n记录的建议操作：{action}",
    ),
    "not_recorded": ("tidak direkodkan", "未记录"),
    "multiple_reviews": (
        "Terdapat beberapa semakan klinik. Baca setiap semakan secara berasingan dan hubungi klinik berkenaan jika cadangan berbeza.",
        "存在多份诊所审核。请分别阅读；如果建议不同，请联系对应的审核诊所。",
    ),
    "review_booking": (
        "Doktor veterinar mengesyorkan pemeriksaan klinik. Semak janji temu sedia ada sebelum memilih masa baharu. Untuk tempahan berkaitan semakan, gunakan Choose appointment time pada semakan tersebut.",
        "兽医建议到诊所检查。选择新时间前请先查看已有预约。若要关联审核，请使用该审核中的 Choose appointment time。",
    ),
    "review_home": (
        "Ikuti arahan penjagaan di rumah yang direkodkan oleh doktor veterinar. Anggaran AI bukan pelan rawatan baharu. Hubungi klinik jika keadaan berubah atau arahan tidak jelas.",
        "请遵循兽医记录的居家护理指示。AI估计不是新的治疗计划。若情况变化或指示不清楚，请联系诊所。",
    ),
    "review_unclear": (
        "Semakan yang direkodkan tidak menetapkan penilaian yang jelas. Hubungi klinik yang menyemak untuk mendapatkan pemeriksaan.",
        "记录中的审核未能得出明确评估。请联系审核诊所，咨询进一步检查。",
    ),
    "next_inconclusive": (
        "Minta semakan veterinar atau hantar gambar baharu yang jelas. Jangan gunakan keputusan tidak konklusif untuk memutuskan bahawa rawatan tidak diperlukan. Teruskan arahan veterinar sedia ada.",
        "可申请兽医审核，或重新上传清晰照片。请勿据不确定结果认定无需治疗，并继续遵循已有兽医指示。",
    ),
    "next_higher": (
        "Aturkan pemeriksaan veterinar; jangan bergantung pada anggaran gambar atau produk pergigian sahaja. Semak janji temu sedia ada sebelum membuat tempahan baharu.",
        "请安排兽医检查，不要仅依赖照片估计或牙齿护理产品。新增预约前请先查看已有预约。",
    ),
    "next_mild": (
        "Anda boleh meminta semakan veterinar untuk nasihat khusus. Anggaran ringan tidak membuktikan bahawa penjagaan di rumah sahaja mencukupi.",
        "可申请兽医审核以获得针对宠物的建议。轻度估计不能证明仅居家护理就足够。",
    ),
    "next_none": (
        "Teruskan nasihat penjagaan pencegahan doktor veterinar dan dapatkan pemeriksaan jika terdapat kebimbangan.",
        "请继续遵循兽医的预防护理建议；如发现异常，请安排检查。",
    ),
    "next_unavailable": (
        "Anggaran keterukan tidak tersedia. Minta semakan veterinar atau hubungi klinik, bukannya meneka rawatan.",
        "严重程度估计不可用。请申请兽医审核或联系诊所，而非猜测需要何种治疗。",
    ),
}

CONDITIONS = {
    "plaque": ("plak gigi", "牙菌斑"),
    "gingivitis": ("radang gusi", "牙龈炎"),
    "calculus": ("karang gigi", "牙结石"),
}
SEVERITIES = {
    "mild": ("ringan", "轻度"),
    "moderate": ("sederhana", "中度"),
    "severe": ("teruk", "重度"),
    "none": ("tiada keterukan diberikan", "未分配严重程度"),
    "inconclusive": ("tidak konklusif", "不确定"),
    "unavailable": ("tidak tersedia", "不可用"),
}


def render_assessment_reply(intent, context, language):
    if language not in {"ms", "zh"} or intent not in SUPPORTED_INTENTS:
        return None
    index = 0 if language == "ms" else 1

    def text(key, **values):
        return TEXT[key][index].format(**values)

    def condition_names(values):
        if not isinstance(values, list):
            return []
        return [CONDITIONS[value][index] for value in values
                if isinstance(value, str) and value in CONDITIONS]

    pet = context.get("pet")
    if not isinstance(pet, dict):
        return text("select_pet")
    name = str(pet.get("name", ""))
    latest = context.get("latest_analysis")
    if not isinstance(latest, dict):
        return text("missing", name=name)

    decision = latest.get("assessment_decision")
    decision = decision if isinstance(decision, dict) else {}
    status = decision.get("status")
    date = latest.get("analysis_date")
    date = date[:10] if isinstance(date, str) else text("date_missing")
    sections = [text("heading", name=name, date=date,
                     analysis_id=latest.get("analysis_id"))]
    if status in {"inconclusive", "healthy_pattern", "unavailable"}:
        sections.append(text(status))
    elif status == "disease_flags":
        flags = condition_names(decision.get("disease_flags"))
        estimate = SEVERITIES.get(latest.get("estimated_severity"),
                                  SEVERITIES["unavailable"])[index]
        sections.append(text("flags", conditions=", ".join(flags) or text("no_flags"),
                             severity=estimate))
    else:
        sections.append(text("unavailable"))

    excluded = condition_names(decision.get("not_assessed_conditions"))
    if excluded:
        sections.append(text("coverage", conditions=", ".join(excluded)))
    sections.append(text("reference"))

    reviews = [review for review in context.get("vet_reviews", [])
               if isinstance(review, dict)
               and review.get("analysis_id") == latest.get("analysis_id")]

    if intent == "pet_next_steps":
        if reviews:
            if len(reviews) > 1:
                key = "multiple_reviews"
            elif reviews[0].get("recommended_action") in {
                "routine_booking", "prompt_clinic_assessment"
            }:
                key = "review_booking"
            elif reviews[0].get("recommended_action") == "home_care":
                key = "review_home"
            else:
                key = "review_unclear"
        else:
            estimate = latest.get("estimated_severity")
            key = {
                "inconclusive": "next_inconclusive", "moderate": "next_higher",
                "severe": "next_higher", "mild": "next_mild", "none": "next_none",
            }.get(estimate, "next_unavailable")
        sections.append(text(key))

    # Preserve every clinic's feedback verbatim, never combine their opinions.
    for review in reviews:
        sections.append(text(
            "review", review_id=review.get("review_id"),
            clinic_id=review.get("clinic_id"),
            feedback=review.get("feedback") or text("not_recorded"),
            severity=review.get("reviewed_severity") or text("not_recorded"),
            action=review.get("recommended_action") or text("not_recorded"),
        ))
    return "\n\n".join(sections)
