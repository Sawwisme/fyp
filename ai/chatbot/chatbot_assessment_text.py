"""Structured Malay/Chinese assessment text. No database or action execution."""

SUPPORTED_INTENTS = {
    "explain_latest_analysis", "explain_pet_severity", "pet_next_steps",
    "dental_analysis_history", "compare_analysis_progress",
    "pet_prediction_scores",
    "pet_segmentation_values",
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

    if intent == "pet_prediction_scores":
        return render_prediction_scores(context, language)

    if intent == "pet_segmentation_values":
        return render_segmentation_values(context, language)

    if intent in {"dental_analysis_history", "compare_analysis_progress"}:
        return render_history_reply(intent, context, language)

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


HISTORY_TEXT = {
    "heading": ("Penilaian AI terkini untuk {name}:", "{name}的近期AI评估："),
    "row": ("• {date} — anggaran keterukan: {severity} (#{analysis_id})",
            "• {date} — 严重程度估计：{severity}（#{analysis_id}）"),
    "empty": ("Tiada rekod penilaian dalam sejarah yang dipulangkan.", "返回的历史中没有评估记录。"),
    "scope": ("Ini ialah sejarah penilaian AI, bukan sejarah perubatan konsultasi penuh.",
              "这是AI评估历史，并非完整的诊疗病历。"),
    "need_two": ("Sekurang-kurangnya dua penilaian lengkap diperlukan untuk membandingkan anggaran {name}.",
                 "至少需要两次完成的评估，才能比较{name}的估计结果。"),
    "comparison": (
        "Penilaian terdahulu {name} ({old_date}, #{old_id}): {old_level}; terkini ({new_date}, #{new_id}): {new_level}.",
        "{name}的上次评估（{old_date}，#{old_id}）：{old_level}；最新评估（{new_date}，#{new_id}）：{new_level}。",
    ),
    "versions": ("Versi model atau kaedah anggaran berbeza atau tidak tersedia. Keputusan ini tidak boleh ditafsirkan sebagai trend keterukan yang boleh dipercayai.",
                 "模型版本或估计方法不同，或版本信息不可用，因此无法将其可靠地解释为严重程度趋势。"),
    "missing": ("Satu nilai keterukan tidak tersedia atau tidak konklusif; tahap tidak boleh dibandingkan.",
                "其中一个严重程度值不可用或不确定，无法比较等级。"),
    "lower": ("Tahap anggaran sistem lebih rendah.", "系统估计等级较低。"),
    "higher": ("Tahap anggaran sistem lebih tinggi.", "系统估计等级较高。"),
    "unchanged": ("Tahap anggaran sistem tidak berubah.", "系统估计等级未变。"),
    "caution": ("Pencahayaan, sudut dan gigi yang kelihatan boleh mempengaruhi keputusan. Ini tidak mengesahkan pemulihan atau kemerosotan klinikal.",
                "光线、角度和可见牙齿的差异会影响结果。这不能确认临床改善或恶化。"),
}


def render_history_reply(intent, context, language):
    index = 0 if language == "ms" else 1

    def text(key, **values):
        return HISTORY_TEXT[key][index].format(**values)

    def date(analysis):
        value = analysis.get("analysis_date")
        return value[:10] if isinstance(value, str) else TEXT["date_missing"][index]

    def level(analysis):
        return SEVERITIES.get(analysis.get("estimated_severity"),
                              SEVERITIES["unavailable"])[index]

    name = str(context["pet"].get("name", ""))
    latest = context["latest_analysis"]
    history = context.get("dental_history", [])
    history = [item for item in history if isinstance(item, dict)]
    if intent == "dental_analysis_history":
        lines = [text("heading", name=name)]
        for analysis in history:
            lines.append(text("row", date=date(analysis), severity=level(analysis),
                              analysis_id=analysis.get("analysis_id")))
        if not history:
            lines.append(text("empty"))
        lines.append(text("scope"))
        return "\n".join(lines)

    if len(history) < 2:
        return text("need_two", name=name)
    previous = history[1]
    lines = [text(
        "comparison", name=name, old_date=date(previous), old_id=previous.get("analysis_id"),
        old_level=level(previous), new_date=date(latest), new_id=latest.get("analysis_id"),
        new_level=level(latest),
    )]
    same_model = (latest.get("model_version") is not None
                  and latest.get("model_version") == previous.get("model_version"))
    same_method = (latest.get("severity_method") is not None
                   and latest.get("severity_method") == previous.get("severity_method"))
    if not same_model or not same_method:
        lines.append(text("versions"))
    else:
        ranks = {"none": 0, "mild": 1, "moderate": 2, "severe": 3}
        old = ranks.get(previous.get("estimated_severity"))
        new = ranks.get(latest.get("estimated_severity"))
        if old is None or new is None:
            lines.append(text("missing"))
        else:
            change = "lower" if new < old else "higher" if new > old else "unchanged"
            lines.append(text(change))
            lines.append(text("caution"))
    return "\n\n".join(lines)

def render_prediction_scores(context, language):
    import math

    ms = language == "ms"
    latest = context["latest_analysis"]
    name = context["pet"].get("name", "")

    labels = {
        "healthy": "Sihat" if ms else "健康",
        "plaque": "Plak gigi" if ms else "牙菌斑",
        "gingivitis": "Gingivitis" if ms else "牙龈炎",
        "calculus": "Karang gigi" if ms else "牙结石",
    }

    heading = (
        f"Skor model tersimpan untuk {name}"
        if ms else
        f"{name} 已保存的模型分数"
    )
    lines = [
        f"{heading} — #{latest.get('analysis_id')}"
    ]

    predictions = latest.get("predictions") or []

    for prediction in predictions:
        if not isinstance(prediction, dict):
            continue

        condition = prediction.get("condition")
        if condition not in labels:
            continue

        assessed = (
            prediction.get("assessed", True) is True
            and prediction.get("supported", True) is True
            and type(prediction.get("positive")) is bool
        )

        if not assessed:
            state = (
                "Tidak dinilai untuk spesies ini; bukan bermaksud tiada penyakit."
                if ms else
                "未对该物种进行评估；这不代表没有该疾病。"
            )
            lines.append(f"• {labels[condition]}: {state}")
            continue

        score = prediction.get("confidence")
        valid_score = (
            type(score) in (int, float)
            and math.isfinite(score)
            and 0 <= score <= 1
        )
        score_text = (
            f"{score * 100:.1f}%"
            if valid_score else
            ("Tidak direkodkan" if ms else "未记录")
        )

        if ms:
            state = (
                "Melebihi ambang model"
                if prediction["positive"] else
                "Di bawah ambang model"
            )
        else:
            state = (
                "达到模型判定阈值"
                if prediction["positive"] else
                "低于模型判定阈值"
            )

        lines.append(
            f"• {labels[condition]}: {score_text} — {state}"
        )

    if len(lines) == 1:
        lines.append(
            "Tiada skor pengelasan direkodkan."
            if ms else "未记录分类分数。"
        )

    lines.append(
        "Ini ialah skor model, bukan tahap keterukan atau kebarangkalian "
        "diagnosis yang dijamin. Keputusan negatif tidak menolak penyakit."
        if ms else
        "这些是模型分数，不是严重程度或保证准确的诊断概率。"
        "未被模型标记不代表可以排除疾病。"
    )

    for review in context.get("vet_reviews") or []:
        if (
            isinstance(review, dict)
            and review.get("analysis_id") == latest.get("analysis_id")
        ):
            label = "Maklum balas veterinar asal" if ms else "兽医反馈原文"
            lines.append(
                f"{label} #{review.get('review_id')} "
                f"(clinic #{review.get('clinic_id')}):\n"
                f"{review.get('feedback') or ''}"
            )

    return "\n\n".join(lines)

def render_segmentation_values(context, language):
    import math

    ms = language == "ms"
    latest = context["latest_analysis"]
    name = context["pet"].get("name", "")
    segmentation = latest.get("segmentation") or {}

    heading = (
        f"Anggaran segmentasi tersimpan untuk {name}"
        if ms else
        f"{name} 已保存的图像分割估计"
    )
    lines = [
        f"{heading} — #{latest.get('analysis_id')}"
    ]

    for key, label_ms, label_zh in [
        (
            "gingivitis_area_percent",
            "Kawasan topeng berkaitan gingivitis",
            "牙龈炎相关掩膜区域",
        ),
        (
            "calculus_area_percent",
            "Kawasan topeng berkaitan karang gigi",
            "牙结石相关掩膜区域",
        ),
    ]:
        value = segmentation.get(key)
        valid = (
            type(value) in (int, float)
            and math.isfinite(value)
            and 0 <= value <= 100
        )

        label = label_ms if ms else label_zh

        if valid:
            measurement = (
                f"kira-kira {value:.2f}% daripada piksel imej dianalisis"
                if ms else
                f"约占已分析图像像素的 {value:.2f}%"
            )
        else:
            measurement = (
                "Tidak direkodkan atau tidak tersedia"
                if ms else
                "未记录或不可用"
            )

        lines.append(f"• {label}: {measurement}")

    lines.append(
        "Ini ialah kawasan imej yang dianggarkan oleh model, bukan "
        "peratusan seluruh mulut yang terjejas atau ukuran keterukan klinikal. "
        "Topeng mungkin tersalah menandakan kawasan. "
        "Nilai yang tiada tidak bermaksud sifar."
        if ms else
        "这些是模型估计的图像区域，并非整个口腔的患病比例，"
        "也不是临床严重程度指标。掩膜可能遗漏或错误标记区域。"
        "缺失的数值不代表零。"
    )

    return "\n\n".join(lines)
