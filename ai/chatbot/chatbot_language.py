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
