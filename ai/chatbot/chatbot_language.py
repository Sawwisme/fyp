import re
SUPPORTED_LANGUAGES = {'en', 'ms', 'zh'}
LANGUAGE_COMMANDS = {'en': {'english', 'use english', 'reply in english', 'switch to english', '英文', '用英文', 'bahasa inggeris'}, 'ms': {'malay', 'bahasa melayu', 'bahasa malaysia', 'use malay', 'reply in malay', 'switch to malay', 'guna bahasa melayu', 'jawab dalam bahasa melayu', '马来文', '用马来文'}, 'zh': {'chinese', 'mandarin', 'use chinese', 'reply in chinese', 'switch to chinese', '中文', '用中文', '请用中文', '用华语', 'bahasa cina'}}
CONFIRMATIONS = {'en': 'English preference saved for this chat. Translated replies are still being added.', 'ms': 'Pilihan Bahasa Melayu telah disimpan untuk perbualan ini. Jawapan terjemahan masih sedang ditambah.', 'zh': '已为此对话保存中文偏好。翻译回复功能仍在添加中。'}

def normalize_language_command(message):
    text = str(message).casefold().strip()
    text = re.sub('[.!?。！？]+$', '', text)
    return ' '.join(text.split())

def requested_language(message):
    text = normalize_language_command(message)
    for language, commands in LANGUAGE_COMMANDS.items():
        if text in commands:
            return language
    return None

def language_preference_reply(language):
    return {'intent': 'language_preference', 'reply': CONFIRMATIONS[language], 'mode': 'rule', 'sources': [], 'similarity': None, 'products': [], 'suggested_questions': [], 'recommended_action': 'NONE', 'language': language}
FAQ_QUESTIONS = {'apa itu plak': ('what is dental plaque', 'ms'), 'apa itu plak gigi': ('what is dental plaque', 'ms'), '什么是牙菌斑': ('what is dental plaque', 'zh'), '牙菌斑是什么': ('what is dental plaque', 'zh'), 'apa itu gingivitis': ('what is gingivitis', 'ms'), 'apa itu radang gusi': ('what is gingivitis', 'ms'), '什么是牙龈炎': ('what is gingivitis', 'zh'), '牙龈炎是什么': ('what is gingivitis', 'zh'), 'apa itu karang gigi': ('what is calculus', 'ms'), 'apa itu tartar': ('what is calculus', 'ms'), '什么是牙结石': ('what is calculus', 'zh'), '牙结石是什么': ('what is calculus', 'zh')}
FAQ_TRANSLATIONS = {'plaque_information': {'ms': 'Plak gigi ialah lapisan bakteria pada permukaan gigi. Apabila terkumpul, plak boleh merengsakan gusi dan menyumbang kepada penyakit periodontal. Penjelasan ini tidak mengesahkan bahawa haiwan anda mempunyai plak. Doktor veterinar boleh memeriksa mulutnya.', 'zh': '牙菌斑是附着在牙齿表面的细菌膜。积聚后可能刺激牙龈，并促使牙周疾病发生。这段说明不能确认您的宠物是否有牙菌斑；兽医可以检查其口腔。'}, 'gingivitis_information': {'ms': 'Gingivitis bermaksud keradangan gusi. Gusi mungkin kemerahan, bengkak atau berdarah, tetapi foto atau chatbot tidak boleh menentukan puncanya. Dapatkan pemeriksaan veterinar jika terdapat perubahan pada gusi haiwan anda.', 'zh': '牙龈炎是指牙龈发炎，可能出现发红、肿胀或出血。仅凭照片或聊天机器人无法确定原因。如果宠物的牙龈出现变化，请安排兽医检查。'}, 'calculus_information': {'ms': 'Karang gigi, juga dipanggil tartar, ialah plak yang mengeras bersama mendapan mineral daripada air liur. Ia berbeza daripada lapisan plak yang lebih lembut. Tanya doktor veterinar tentang pemeriksaan dan pembersihan yang sesuai untuk haiwan anda.', 'zh': '牙结石是牙菌斑与唾液中的矿物质形成的硬化沉积物，与较软的牙菌斑不同。请向兽医咨询适合宠物的检查和清洁方式。'}}

def prepare_multilingual_question(message, language):
    text = normalize_language_command(message)
    command = CONVERSATION_COMMANDS.get(text)
    if command is not None:
        return command
    match = FAQ_QUESTIONS.get(text)
    if match is not None:
        return match
    mixed_match = match_mixed_faq(message, language)
    if mixed_match is not None:
        return mixed_match
    return message, language


def localize_faq_answer(answer, language):
    result = dict(answer)
    intent = result.get("intent")

    # Translate only known navigation rules. Never overwrite an urgent
    # or medication rule response with a general-purpose translation.
    control_translation = CONVERSATION_TRANSLATIONS.get(intent, {}).get(language)
    if control_translation and result.get("mode") == "rule":
        result["reply"] = control_translation
        return result

    if result.get("mode") == "rule":
        return result

    if intent == "clarify" and result.get("reply") == FOLLOWUP_CLARIFICATION:
        result["reply"] = FOLLOWUP_CLARIFICATION_TRANSLATIONS.get(
            language, result["reply"]
        )
        return result

    translation = FAQ_TRANSLATIONS.get(intent, {}).get(language)
    if translation:
        result["reply"] = translation
    return result


# Match a complete definition/explanation request. Never extract only a
# disease term from a longer message containing symptoms or instructions.
FAQ_TERM_PATTERNS = {
    "what is dental plaque": (
        r"dental\s+plaque|plaque|牙菌斑|牙斑|plak(?:\s+gigi)?"
    ),
    "what is gingivitis": (
        r"gingivitis|牙龈炎|牙齦炎|radang\s+gusi"
    ),
    "what is calculus": (
        r"dental\s+calculus|calculus|tartar|牙结石|牙結石|karang\s+gigi"
    ),
}


def match_mixed_faq(message, language):
    casual_match = match_casual_multilingual_faq(message, language)
    if casual_match is not None:
        return casual_match
    text = normalize_language_command(message)

    for canonical, term in FAQ_TERM_PATTERNS.items():
        term = rf"(?:{term})"
        polite = (
            r"(?:请问|請問|请|請)?\s*"
            r"(?:(?:你|您)?\s*(?:可以|能不能|能否|能)?\s*"
            r"(?:跟我|给我|給我|告诉我|告訴我)?\s*"
            r"(?:讲一下|講一下|解释一下|解釋一下|解释|解釋|"
            r"介绍一下|介紹一下|说一下|說一下)?\s*)?"
        )
        chinese_patterns = (
            polite + rf"(?:什么是|什麼是|甚麼是)\s*{term}\s*(?:吗|嗎|呢)?",
            polite + rf"{term}\s*(?:是什么|是什麼|是甚麼|是什么意思|是什麼意思)\s*(?:吗|嗎|呢)?",
            r"(?:请问|請問|请|請)?\s*(?:(?:你|您)?\s*(?:可以|能不能|能否|能)?\s*"
            r"(?:跟我|给我|給我)?\s*)?"
            rf"(?:讲一下|講一下|解释一下|解釋一下|解释|解釋|介绍一下|介紹一下)\s*{term}\s*(?:吗|嗎|呢)?",
        )
        if any(re.fullmatch(pattern, text) for pattern in chinese_patterns):
            return canonical, "zh"

        english_pattern = (
            r"(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?"
            rf"(?:what\s+is|what's|explain|tell\s+me\s+about)\s+{term}"
            r"(?:\s+please)?"
        )
        if re.fullmatch(english_pattern, text):
            response_language = (
                "zh" if re.search(r"[\u3400-\u9fff]", text) else language
            )
            return canonical, response_language

        malay_pattern = (
            r"(?:tolong\s+)?(?:boleh\s+)?"
            rf"(?:apa\s+itu|(?:terangkan|jelaskan)(?:\s+apa\s+itu)?)\s+{term}"
        )
        if re.fullmatch(malay_pattern, text):
            return canonical, "ms"

    return None


def match_casual_multilingual_faq(message, language):
    text = normalize_language_command(message)
    preferred = language if language in SUPPORTED_LANGUAGES else "en"

    for canonical, aliases in FAQ_TERM_PATTERNS.items():
        term = rf"(?:{aliases})"

        malay_patterns = (
            rf"{term}\s+(?:tu|ni|itu|ini)\s+apa(?:\s+(?:ya|eh))?",
            rf"apa\s+(?:maksud|itu|tu)\s+{term}(?:\s+(?:tu|ni|ya))?",
            r"(?:saya|sy|aku)\s+(?:nak|nk|mahu)\s+tahu\s+"
            rf"(?:apa\s+itu|apa\s+maksud)\s+{term}",
        )
        if any(re.fullmatch(pattern, text) for pattern in malay_patterns):
            return canonical, "ms"

        explanation = (
            r"(?:tolong\s+)?(?:(?:boleh|blh)\s+)?"
            r"(?:explain|terangkan|jelaskan|cerita)"
            r"(?:\s+(?:tentang|pasal))?\s+"
            + term
            + r"(?:\s+(?:sikit|sedikit))?(?:\s+(?:tak|boleh|pls|please))?"
        )
        has_malay_structure = re.search(
            r"\b(?:tolong|boleh|blh|terangkan|jelaskan|cerita|tentang|pasal|sikit|sedikit|tak)\b",
            text,
        )
        if has_malay_structure and re.fullmatch(explanation, text):
            # Chinese disease names do not make a Malay question Chinese.
            return canonical, "ms"

        three_language = (
            r"(?:boleh|blh)\s+(?:explain|terangkan)(?:一下)?\s*"
            + term
            + r"\s*(?:是什么|是什麼|吗|嗎|呢)?"
        )
        chinese_grammar = re.search(r"一下|是什么|是什麼|吗|嗎|呢", text)
        if chinese_grammar and re.fullmatch(three_language, text):
            return canonical, preferred

        chinese_explanation = (
            r"(?:请|請)?\s*(?:(?:你|您)\s*)?"
            r"(?:可以|能不能|能否|能)?\s*(?:跟我|给我|給我)?\s*"
            r"explain(?:一下)?\s*" + term + r"\s*(?:吗|嗎|呢)?"
        )
        if re.search(r"[\u3400-\u9fff]", text) and re.fullmatch(chinese_explanation, text):
            return canonical, "zh"

        ambiguous_english = (
            r"(?:please\s+)?(?:what\s+is|explain|tell\s+me\s+about)\s+"
            + term + r"\s+(?:lah|la)"
        )
        if re.fullmatch(ambiguous_english, text):
            return canonical, preferred

    return None


# Whole-message aliases only: topic navigation is not appointment cancellation.
CONVERSATION_COMMANDS = {
    "解释一下": ("explain that", "zh"),
    "解釋一下": ("explain that", "zh"),
    "再解释一下": ("explain that", "zh"),
    "再说一次": ("repeat that", "zh"),
    "再說一次": ("repeat that", "zh"),
    "上一次呢": ("what about the previous one", "zh"),
    "上次的结果呢": ("what about the previous one", "zh"),
    "上次的結果呢": ("what about the previous one", "zh"),
    "严重吗": ("how severe is it", "zh"),
    "嚴重嗎": ("how severe is it", "zh"),
    "换个话题": ("change topic", "zh"),
    "換個話題": ("change topic", "zh"),
    "重新开始": ("start over", "zh"),
    "重新開始": ("start over", "zh"),
    "换宠物": ("switch pet", "zh"),
    "換寵物": ("switch pet", "zh"),
    "选择另一只宠物": ("select another pet", "zh"),
    "第一个": ("first one", "zh"),
    "第一個": ("first one", "zh"),
    "第二个": ("second one", "zh"),
    "第二個": ("second one", "zh"),
    "terangkan lagi": ("explain that", "ms"),
    "jelaskan lagi": ("explain that", "ms"),
    "explain lagi": ("explain that", "ms"),
    "ulang semula": ("repeat that", "ms"),
    "keputusan sebelum ini": ("what about the previous one", "ms"),
    "keputusan yang lepas": ("what about the previous one", "ms"),
    "teruk ke": ("how severe is it", "ms"),
    "berapa teruk": ("how severe is it", "ms"),
    "tukar topik": ("change topic", "ms"),
    "topik baru": ("new topic", "ms"),
    "mula semula": ("start over", "ms"),
    "tukar haiwan": ("switch pet", "ms"),
    "pilih haiwan lain": ("select another pet", "ms"),
    "yang pertama": ("first one", "ms"),
    "pilihan pertama": ("first one", "ms"),
    "yang kedua": ("second one", "ms"),
    "pilihan kedua": ("second one", "ms"),
}

CONVERSATION_TRANSLATIONS = {
    "conversation_reset": {
        "ms": "Baik, kita mulakan topik baharu. Apa yang boleh saya bantu?",
        "zh": "好的，我们换个话题。您想了解什么？",
    },
    "change_pet": {
        "ms": (
            "Haiwan yang mana? Tekan Select pet di bawah untuk membuka "
            "perbualan baharu bagi pilihan anda. Sehingga itu, perbualan "
            "ini masih dikaitkan dengan haiwan semasa."
        ),
        "zh": (
            "您指的是哪只宠物？请点击下方的 Select pet，"
            "为所选宠物打开新对话。在此之前，本对话仍关联当前宠物。"
        ),
    },
}

FOLLOWUP_CLARIFICATION = (
    "Which topic do you mean: your pet's AI result, "
    "estimated severity, previous assessment, appointment, "
    "heatmap or segmentation?"
)

FOLLOWUP_CLARIFICATION_TRANSLATIONS = {
    "ms": (
        "Topik yang mana: keputusan AI haiwan anda, anggaran keterukan, "
        "penilaian terdahulu, janji temu, peta haba atau segmentasi?"
    ),
    "zh": "您指哪个主题：宠物的AI结果、估计严重程度、之前的评估、预约、热力图，还是分割结果？",
}


# Complete record requests only; additional symptoms must not be discarded.
FAQ_QUESTIONS.update({
    "解释我的最新扫描结果": ("explain my latest result", "zh"),
    "解釋我的最新掃描結果": ("explain my latest result", "zh"),
    "解释我的最新评估": ("explain my latest result", "zh"),
    "我的scan结果怎么样": ("explain my latest result", "zh"),
    "我的扫描结果怎么样": ("explain my latest result", "zh"),
    "我的宠物情况严重吗": ("how severe is my pet condition", "zh"),
    "扫描后应该做什么": ("what should I do after my dental scan", "zh"),
    "我接下来应该做什么": ("what should I do after my dental scan", "zh"),
    "terangkan keputusan imbasan terkini": ("explain my latest result", "ms"),
    "jelaskan keputusan scan saya": ("explain my latest result", "ms"),
    "keputusan scan saya macam mana": ("explain my latest result", "ms"),
    "berapa teruk keadaan haiwan saya": ("how severe is my pet condition", "ms"),
    "apa perlu buat selepas scan": ("what should I do after my dental scan", "ms"),
    "apa saya perlu buat selepas imbasan gigi": ("what should I do after my dental scan", "ms"),
})


FAQ_QUESTIONS.update({
    "显示评估历史": ("show my pet previous results", "zh"),
    "我的扫描历史": ("show my pet previous results", "zh"),
    "查看扫描历史": ("show my pet previous results", "zh"),
    "比较最新和上次结果": ("compare my latest scan with the earlier one", "zh"),
    "比较两次扫描": ("compare my latest scan with the earlier one", "zh"),
    "sejarah scan saya": ("show my pet previous results", "ms"),
    "tunjuk sejarah penilaian": ("show my pet previous results", "ms"),
    "bandingkan keputusan scan": ("compare my latest scan with the earlier one", "ms"),
    "bandingkan dengan keputusan sebelum ini": ("compare my latest scan with the earlier one", "ms"),
})

def render_upcoming_appointments(
    pet_name,
    records,
    rearrangement_ids=(),
    language="en",
):
    labels = {
        "en": {
            "select": "Select a pet to check its appointments.",
            "empty": "No upcoming appointment was found for {name}. Open Booking to check all appointments.",
            "heading": "Upcoming bookings for {name} (Malaysia time):",
            "appointment": "Appointment",
            "date": "Date",
            "clinic": "Clinic",
            "vet": "Veterinarian",
            "type": "Type",
            "status": "Status",
            "address": "Address",
            "missing": "Not recorded",
            "rearrange": (
                "This appointment needs rearrangement because of "
                "a reported veterinarian absence. Contact the clinic."
            ),
            "footer": (
                "Open Booking to view or manage these appointments. "
                "This chat has not created or changed a booking."
            ),
        },
        "ms": {
            "select": "Pilih haiwan untuk menyemak janji temunya.",
            "empty": "Tiada janji temu akan datang untuk {name}. Buka Booking untuk menyemak semua janji temu.",
            "heading": "Tempahan akan datang untuk {name} (waktu Malaysia):",
            "appointment": "Janji temu",
            "date": "Tarikh",
            "clinic": "Klinik",
            "vet": "Doktor veterinar",
            "type": "Jenis",
            "status": "Status",
            "address": "Alamat",
            "missing": "Tidak direkodkan",
            "rearrange": (
                "Janji temu ini perlu dijadualkan semula kerana "
                "ketidakhadiran doktor veterinar yang dilaporkan. "
                "Hubungi klinik."
            ),
            "footer": (
                "Buka Booking untuk melihat atau mengurus janji temu. "
                "Perbualan ini tidak mencipta atau mengubah tempahan."
            ),
        },
        "zh": {
            "select": "请先选择宠物，再查看其预约。",
            "empty": "没有找到{name}即将到来的预约。请打开 Booking 查看全部预约。",
            "heading": "{name}即将到来的预约（马来西亚时间）：",
            "appointment": "预约",
            "date": "日期",
            "clinic": "诊所",
            "vet": "兽医",
            "type": "类型",
            "status": "状态",
            "address": "地址",
            "missing": "未记录",
            "rearrange": (
                "因已报告的兽医缺勤，此预约需要重新安排。"
                "请联系诊所。"
            ),
            "footer": (
                "请打开 Booking 查看或管理预约。"
                "本次聊天没有创建或更改预约。"
            ),
        },
    }

    statuses = {
        "en": {
            "pending": "Pending clinic confirmation",
            "confirmed": "Confirmed",
            "pending_payment": "Awaiting payment — not confirmed",
        },
        "ms": {
            "pending": "Menunggu pengesahan klinik",
            "confirmed": "Disahkan",
            "pending_payment": "Menunggu bayaran — belum disahkan",
        },
        "zh": {
            "pending": "等待诊所确认",
            "confirmed": "已确认",
            "pending_payment": "等待付款 — 尚未确认",
        },
    }

    language = language if language in labels else "en"
    text = labels[language]

    if pet_name is None:
        return text["select"]

    if not records:
        return text["empty"].format(name=pet_name)

    sections = [text["heading"].format(name=pet_name)]

    for record in records:
        appointment_id = record["appointment_id"]
        date = record["schedule_date"].strftime("%d %b %Y")
        start = record["start_time"].strftime("%H:%M")
        end = record["end_time"].strftime("%H:%M")
        status = statuses[language].get(
            record["status"],
            record["status"],
        )

        section = (
            f"{text['appointment']} #{appointment_id}\n"
            f"{text['date']}: {date}, {start}–{end}\n"
            f"{text['clinic']}: {record['clinic_name']}\n"
            f"{text['vet']}: {record['vet_name']}\n"
            f"{text['type']}: {record['appointment_type']}\n"
            f"{text['status']}: {status}\n"
            f"{text['address']}: "
            f"{record['address'] or text['missing']}"
        )

        if appointment_id in rearrangement_ids:
            section += "\n" + text["rearrange"]

        sections.append(section)

    sections.append(text["footer"])
    return "\n\n".join(sections)

FAQ_QUESTIONS.update({
    "我的下一次预约": ("when is my next appointment", "zh"),
    "查看我的预约": ("when is my next appointment", "zh"),
    "我的appointment是什么时候": ("when is my next appointment", "zh"),
    "bila appointment saya": ("when is my next appointment", "ms"),
    "bila janji temu saya": ("when is my next appointment", "ms"),
    "tunjuk appointment saya": ("when is my next appointment", "ms"),
})

def render_followup_care(pet_name, tasks, language="en"):
    labels = {
        "en": {
            "select": "Select a pet to check its follow-up care.",
            "empty": "No open follow-up task was found for {name}.",
            "heading": "Open follow-up tasks for {name}:",
            "task": "Follow-up",
            "clinic": "Clinic",
            "status": "Status",
            "date": "Recommended review date",
            "reason": "Recorded reason",
            "care": "Vet instructions — original text",
            "photos": "Photo instructions — original text",
            "missing": "Not recorded",
            "submit": "You can submit an update through this task.",
            "wait": "Another submission is not currently allowed. Check the task for feedback.",
            "visit": "An in-clinic review is required. Check the linked appointment before booking another visit.",
            "footer": "A recommended review date is not a booked appointment. This chat has not submitted photos or changed a follow-up.",
        },
        "ms": {
            "select": "Pilih haiwan untuk menyemak penjagaan susulannya.",
            "empty": "Tiada tugasan susulan terbuka untuk {name}.",
            "heading": "Tugasan susulan terbuka untuk {name}:",
            "task": "Susulan",
            "clinic": "Klinik",
            "status": "Status",
            "date": "Tarikh pemeriksaan semula yang disyorkan",
            "reason": "Sebab yang direkodkan",
            "care": "Arahan veterinar — teks asal",
            "photos": "Arahan foto — teks asal",
            "missing": "Tidak direkodkan",
            "submit": "Anda boleh menghantar kemas kini melalui tugasan ini.",
            "wait": "Penghantaran lain belum dibenarkan. Semak tugasan untuk maklum balas.",
            "visit": "Pemeriksaan di klinik diperlukan. Semak janji temu berkaitan sebelum membuat tempahan lain.",
            "footer": "Tarikh pemeriksaan yang disyorkan bukan janji temu yang telah ditempah. Perbualan ini tidak menghantar foto atau mengubah susulan.",
        },
        "zh": {
            "select": "请先选择宠物，再查看后续护理。",
            "empty": "没有找到{name}尚未结束的后续护理任务。",
            "heading": "{name}尚未结束的后续护理任务：",
            "task": "后续护理",
            "clinic": "诊所",
            "status": "状态",
            "date": "建议复查日期",
            "reason": "记录的原因",
            "care": "兽医指示 — 原文",
            "photos": "照片要求 — 原文",
            "missing": "未记录",
            "submit": "您可以通过此任务提交更新。",
            "wait": "目前不允许再次提交。请查看任务中的审核反馈。",
            "visit": "需要到诊所复查。新增预约前，请先查看关联预约。",
            "footer": "建议复查日期不代表已预约。本次聊天没有提交照片或更改后续护理任务。",
        },
    }

    states = {
        "action_needed": (
            "An update can be submitted",
            "Kemas kini boleh dihantar",
            "可以提交更新",
        ),
        "awaiting_review": (
            "Awaiting vet review",
            "Menunggu semakan veterinar",
            "等待兽医审核",
        ),
        "update_requested": (
            "Another update requested",
            "Kemas kini tambahan diminta",
            "兽医要求再次更新",
        ),
        "visit_required": (
            "In-clinic review required",
            "Pemeriksaan di klinik diperlukan",
            "需要到诊所复查",
        ),
        "reviewed": (
            "Reviewed",
            "Telah disemak",
            "已审核",
        ),
        "completed": ("Completed", "Selesai", "已完成"),
        "cancelled": ("Cancelled", "Dibatalkan", "已取消"),
    }

    language = language if language in labels else "en"
    index = {"en": 0, "ms": 1, "zh": 2}[language]
    text = labels[language]

    if pet_name is None:
        return text["select"]

    if not tasks:
        return text["empty"].format(name=pet_name)

    sections = [text["heading"].format(name=pet_name)]

    for task in tasks:
        state = states.get(task["state"])
        status = state[index] if state else text["missing"]

        section = (
            f"{text['task']} #{task['followup_id']}\n"
            f"{text['clinic']}: {task['clinic_name']}\n"
            f"{text['status']}: {status}\n"
            f"{text['date']}: {task['date'] or text['missing']}\n"
            f"{text['reason']}: {task['reason'] or text['missing']}\n"
            f"{text['care']}: "
            f"{task['care_instructions'] or text['missing']}"
        )

        if task["photos_required"]:
            section += (
                f"\n{text['photos']}: "
                f"{task['photo_instructions'] or text['missing']}"
            )

        section += "\n" + (
            text["submit"] if task["can_submit"] else text["wait"]
        )

        if task["visit_required"]:
            section += "\n" + text["visit"]

        sections.append(section)

    sections.append(text["footer"])
    return "\n\n".join(sections)

FAQ_QUESTIONS.update({
    "查看后续护理": ("show my pet follow up instructions", "zh"),
    "我的复查情况": ("show my pet follow up instructions", "zh"),
    "follow up现在怎样": ("show my pet follow up instructions", "zh"),
    "semak penjagaan susulan": ("show my pet follow up instructions", "ms"),
    "status follow up saya": ("show my pet follow up instructions", "ms"),
})

def render_product_match_reason(
    *,
    species,
    age_months,
    minimum_age_months,
    category_name,
    category_requested,
    budget,
    matched_tags,
    source,
    language="en",
):
    if language not in {"ms", "zh"}:
        return None

    index = 0 if language == "ms" else 1

    phrases = {
        "unknown_age": (
            "Disenaraikan untuk {species} tanpa had umur minimum. "
            "Umur haiwan belum direkodkan; semak label penuh.",
            "产品适用于{species}，且未设最低年龄限制。"
            "宠物年龄未记录；请查看完整产品标签。",
        ),
        "known_age": (
            "Sepadan dengan spesies ({species}) dan umur "
            "({age} bulan) yang direkodkan. "
            "Umur minimum produk: {minimum} bulan.",
            "符合记录的物种（{species}）和年龄（{age}个月）。"
            "产品最低适用年龄：{minimum}个月。",
        ),
        "category": (
            "Sepadan dengan kategori yang diminta: {category}.",
            "符合所请求的类别：{category}。",
        ),
        "budget": (
            "Dalam bajet RM {budget:.2f} bagi setiap item.",
            "在每件 RM {budget:.2f} 的预算内。",
        ),
        "purpose": (
            "Tujuan penjagaan yang sepadan: {purposes}. "
            "Sumber: {source}.",
            "匹配的护理用途：{purposes}。依据：{source}。",
        ),
        "warning": (
            "Dipilih secara automatik oleh chatbot sebagai pilihan "
            "penjagaan sokongan, bukan preskripsi atau pengganti "
            "rawatan. Semak label dan arahan veterinar. Produk "
            "kawalan plak tidak ditunjukkan sebagai membuang "
            "karang gigi sedia ada.",
            "由聊天机器人自动匹配，作为辅助护理选择，"
            "并非处方或治疗替代品。请查看产品标签和兽医指示。"
            "控菌斑产品不代表能够去除已有牙结石。",
        ),
    }

    species_names = {
        "cat": ("kucing", "猫"),
        "dog": ("anjing", "狗"),
    }

    purpose_names = {
        "routine_oral_hygiene": (
            "kebersihan mulut rutin", "日常口腔清洁"
        ),
        "plaque_control": ("kawalan plak", "牙菌斑控制"),
        "breath_freshening": ("penjagaan bau nafas", "口气护理"),
    }

    species_name = species_names.get(
        species, (species, species)
    )[index]

    if age_months is None:
        sections = [
            phrases["unknown_age"][index].format(
                species=species_name
            )
        ]
    else:
        sections = [
            phrases["known_age"][index].format(
                species=species_name,
                age=age_months,
                minimum=minimum_age_months,
            )
        ]

    if category_requested:
        sections.append(
            phrases["category"][index].format(
                category=category_name
            )
        )

    if budget is not None:
        sections.append(
            phrases["budget"][index].format(budget=budget)
        )

    purposes = [
        purpose_names[tag][index]
        for tag in matched_tags
        if tag in purpose_names
    ]

    if purposes:
        sections.append(
            phrases["purpose"][index].format(
                purposes=", ".join(purposes),
                source=source,
            )
        )

    sections.append(phrases["warning"][index])
    return " ".join(sections)

def render_product_search_reply(
    *,
    language="en",
    pet_name="",
    count=0,
    source="",
    categories=(),
    budget=None,
    review_note=None,
    explanation=None,
    no_match=False,
):
    if language not in {"ms", "zh"}:
        return None

    index = 0 if language == "ms" else 1

    text = {
        "no_match": (
            "Tiada produk tersedia yang sepadan dengan jenis produk, "
            "bajet dan kriteria spesies/umur haiwan yang direkodkan. "
            "Cuba jenis produk atau bajet lain, atau semak kedai klinik.",
            "没有可用产品符合所请求的产品类型、预算，"
            "以及宠物记录中的物种和年龄条件。"
            "可尝试其他产品类型或预算，或浏览诊所商店。",
        ),
        "found": (
            "Saya menemui {count} pilihan produk penjagaan untuk "
            "{name}. Sumber padanan: {source}.",
            "为{name}找到{count}个护理产品选项。匹配依据：{source}。",
        ),
        "review": (
            "Nota semakan/rekod — teks asal:",
            "审核／记录说明 — 原文：",
        ),
        "explanation": (
            "Penjelasan padanan — teks asal:",
            "匹配说明 — 原文：",
        ),
        "categories": (
            "Jenis produk: {categories}.",
            "产品类型：{categories}。",
        ),
        "budget": (
            "Bajet: sehingga RM {budget:.2f} bagi setiap item.",
            "预算：每件最高 RM {budget:.2f}。",
        ),
        "footer": (
            "Kad di bawah menerangkan setiap padanan. Ini ialah "
            "cadangan penjagaan di rumah secara automatik, bukan "
            "preskripsi atau pengganti rawatan. Semak label produk "
            "dan arahan veterinar.",
            "下方卡片说明每个匹配原因。这些是自动生成的居家护理建议，"
            "并非处方或治疗替代品。请查看产品标签和兽医指示。",
        ),
    }

    if no_match:
        return text["no_match"][index]

    sections = []

    if review_note:
        sections.append(
            text["review"][index] + "\n" + review_note
        )

    sections.append(
        text["found"][index].format(
            count=count,
            name=pet_name,
            source=source,
        )
    )

    if explanation:
        sections.append(
            text["explanation"][index] + "\n" + explanation
        )

    if categories:
        sections.append(
            text["categories"][index].format(
                categories=", ".join(categories)
            )
        )

    if budget is not None:
        sections.append(
            text["budget"][index].format(budget=budget)
        )

    sections.append(text["footer"][index])
    return "\n\n".join(sections)

FAQ_QUESTIONS.update({
    "推荐牙齿护理产品": (
        "recommend dental care products", "zh"
    ),
    "推荐刷牙用品": (
        "recommend products for routine brushing", "zh"
    ),
    "推荐控制牙菌斑的产品": (
        "recommend products for plaque control", "zh"
    ),
    "cadangkan produk penjagaan gigi": (
        "recommend dental care products", "ms"
    ),
    "cadangkan produk untuk memberus gigi": (
        "recommend products for routine brushing", "ms"
    ),
    "cadangkan produk untuk kawalan plak": (
        "recommend products for plaque control", "ms"
    ),
})