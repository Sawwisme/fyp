import re
SUPPORTED_LANGUAGES = {'en', 'ms', 'zh'}
LANGUAGE_COMMANDS = {'en': {'english', 'use english', 'reply in english', 'switch to english', '英文', '用英文', 'bahasa inggeris'}, 'ms': {'malay', 'bahasa melayu', 'bahasa malaysia', 'use malay', 'reply in malay', 'switch to malay', 'guna bahasa melayu', 'jawab dalam bahasa melayu', '马来文', '用马来文'}, 'zh': {'chinese', 'mandarin', 'use chinese', 'reply in chinese', 'switch to chinese', '中文', '用中文', '请用中文', '用华语', 'bahasa cina'}}
CONFIRMATIONS = {'en': 'English preference saved for this chat. Translated replies are still being added.', 'ms': 'Pilihan Bahasa Melayu telah disimpan untuk perbualan ini. Jawapan terjemahan masih sedang ditambah.', 'zh': '已为此对话保存中文偏好。翻译回复功能仍在添加中。'}

def normalize_language_command(message):
    text = str(message).casefold().strip()
    text = re.sub(
        '[.!?。！？]+$', 
        '', 
        text
    )
    return ' '.join(text.split())

def requested_language(message):
    text = normalize_language_command(message)
    for language, commands in LANGUAGE_COMMANDS.items():
        if text in commands:
            return language
    return None

def language_preference_reply(language):
    return {
        'intent': 'language_preference', 
        'reply': CONFIRMATIONS[language], 
        'mode': 'rule', 'sources': [], 
        'similarity': None, 'products': [], 
        'suggested_questions': [], 
        'recommended_action': 'NONE', 
        'language': language
        }

FAQ_QUESTIONS = {
    'apa itu plak': (
        'what is dental plaque', 
        'ms'
    ), 
    'apa itu plak gigi': (
            'what is dental plaque', 
            'ms'
    ), 
    '什么是牙菌斑': (
        'what is dental plaque', 
        'zh'
    ),
    '牙菌斑是什么': (
        'what is dental plaque', 
        'zh'
    ), 
    'apa itu gingivitis': (
        'what is gingivitis', 
        'ms'
    ), 
    'apa itu radang gusi': (
        'what is gingivitis', 
        'ms'
    ), 
    '什么是牙龈炎': (
        'what is gingivitis', 
        'zh'
    ), 
    '牙龈炎是什么': (
        'what is gingivitis', 
        'zh'
        ), 
    'apa itu karang gigi': (
        'what is calculus', 
        'ms'
    ), 
    'apa itu tartar': (
        'what is calculus', 
        'ms'
    ), 
    '什么是牙结石': (
        'what is calculus', 
        'zh'
    ), 
    '牙结石是什么': (
        'what is calculus', 
        'zh'
    )
}

FAQ_TRANSLATIONS = {
    "plaque_information": {
        "ms": (
            "Plak gigi ialah lapisan bakteria pada permukaan gigi. "
            "Apabila terkumpul, plak boleh merengsakan gusi dan "
            "menyumbang kepada penyakit periodontal. Penjelasan ini "
            "tidak mengesahkan bahawa haiwan anda mempunyai plak. "
            "Doktor veterinar boleh memeriksa mulutnya."
        ),
        "zh": (
            "牙菌斑是附着在牙齿表面的细菌膜。积聚后可能刺激牙龈，"
            "并促使牙周疾病发生。这段说明不能确认您的宠物是否有牙菌斑；"
            "兽医可以检查其口腔。"
        ),
    },
    "gingivitis_information": {
        "ms": (
            "Gingivitis bermaksud keradangan gusi. Gusi mungkin "
            "kemerahan, bengkak atau berdarah, tetapi foto atau "
            "chatbot tidak boleh menentukan puncanya. Dapatkan "
            "pemeriksaan veterinar jika terdapat perubahan pada "
            "gusi haiwan anda."
        ),
        "zh": (
            "牙龈炎是指牙龈发炎，可能出现发红、肿胀或出血。"
            "仅凭照片或聊天机器人无法确定原因。如果宠物的牙龈出现变化，"
            "请安排兽医检查。"
        ),
    },
    "calculus_information": {
        "ms": (
            "Karang gigi, juga dipanggil tartar, ialah plak yang "
            "mengeras bersama mendapan mineral daripada air liur. "
            "Ia berbeza daripada lapisan plak yang lebih lembut. "
            "Tanya doktor veterinar tentang pemeriksaan dan "
            "pembersihan yang sesuai untuk haiwan anda."
        ),
        "zh": (
            "牙结石是牙菌斑与唾液中的矿物质形成的硬化沉积物，"
            "与较软的牙菌斑不同。请向兽医咨询适合宠物的检查和清洁方式。"
        ),
    },
}

FAQ_TRANSLATIONS.update({
    "ai_interpretation": {
        "ms": (
            "Keputusan AI VetDental ialah rujukan saringan, bukan "
            "diagnosis yang disahkan. Skor model bukan ukuran tahap "
            "keterukan penyakit. Jika dapatan membimbangkan anda, "
            "buka penilaian yang telah selesai dan pilih "
            "Book a dental examination. Dapatan veterinar "
            "direkodkan secara berasingan daripada keputusan AI asal."
        ),
        "zh": (
            "VetDental 的 AI 结果仅供筛查参考，并非确诊。"
            "模型分数不代表疾病严重程度。如果结果让您担心，"
            "请打开已完成的评估，选择 Book a dental examination。"
            "兽医检查结果会与原始 AI 结果分开记录。"
        ),
    },
    "request_review": {
        "ms": (
            "Untuk membincangkan dapatan AI dengan veterinar, "
            "buka penilaian yang telah selesai dan pilih "
            "Book a dental examination. Pilih klinik, veterinar "
            "dan masa yang tersedia, kemudian semak butiran "
            "dan sahkan tempahan anda."
        ),
        "zh": (
            "如需与兽医讨论 AI 发现，请打开已完成的评估，"
            "选择 Book a dental examination。"
            "选择诊所、兽医和可预约时间，"
            "然后检查详情并确认预约。"
        ),
    },
    "cancel_appointment": {
        "ms": (
            "Buka Booking dan pilih janji temu yang ingin diuruskan. "
            "Gunakan tindakan pembatalan jika tersedia. Sistem akan "
            "menyemak sama ada janji temu masih boleh dibatalkan. "
            "Chatbot tidak boleh membatalkan janji temu atau mengesahkan "
            "kelayakan bayaran balik melalui perbualan ini. Semak "
            "butiran janji temu dan pembayaran."
        ),
        "zh": (
            "打开 Booking，选择需要管理的预约。"
            "如果提供取消操作，请使用该操作。"
            "系统会检查预约是否仍可取消。"
            "聊天机器人不能在此对话中取消预约或确认退款资格。"
            "请查看预约和付款详情。"
        ),
    },
    "followup_update": {
        "ms": (
            "Buka Follow-up Care melalui Booking dan pilih tugasan "
            "yang berkaitan. Baca arahan veterinar dan hantar foto "
            "atau perkembangan apabila tugasan membenarkannya. "
            "Selepas penghantaran, semak maklum balas dalam tugasan "
            "tersebut. Penghantaran seterusnya mungkin memerlukan "
            "permintaan kemas kini tambahan daripada veterinar."
        ),
        "zh": (
            "从 Booking 打开 Follow-up Care，选择相关任务。"
            "阅读兽医指示，并在任务允许时提交照片或恢复情况。"
            "提交后，请在任务中查看反馈。再次提交可能需要"
            "兽医先请求补充更新。"
        ),
    },
})

FAQ_TRANSLATIONS.update({
    "explain_gradcam": {
        "ms": (
            "Peta haba Grad-CAM menunjukkan kawasan imej yang paling "
            "mempengaruhi pengelasan AI. Warna lebih panas menunjukkan "
            "perhatian relatif yang lebih kuat. Kotak berlabel menunjukkan "
            "kawasan perhatian berkaitan ramalan, bukan sempadan penyakit "
            "yang disahkan. Warna merah tidak bermaksud penyakit teruk. "
            "Peta haba tidak boleh mengukur berapa banyak bahagian mulut "
            "haiwan anda yang terjejas."
        ),
        "zh": (
            "Grad-CAM 热力图显示对 AI 分类影响较大的图像区域。"
            "暖色表示相对较强的模型关注程度。带标签的方框表示"
            "与预测相关的关注区域，并非已确认的病变边界。"
            "红色不代表疾病严重，也不能用热力图测量"
            "宠物整个口腔受影响的比例。"
        ),
    },
    "explain_segmentation": {
        "ms": (
            "Segmentasi menganggarkan kawasan imej yang berkaitan "
            "dengan gingivitis dan karang gigi. Berbeza daripada peta "
            "haba pengelasan, segmentasi meramalkan topeng bagi kawasan "
            "tersebut. Ia boleh terlepas kawasan atau menandakan objek "
            "yang tidak berkaitan. Peratus kawasan merujuk kepada piksel "
            "dalam foto yang dihantar, bukan peratus keseluruhan mulut "
            "yang terjejas. Topeng ini membantu tafsiran imej dan bukan "
            "ukuran klinikal yang tepat. Untuk nilai yang disimpan, "
            "pilih haiwan dan tanya: Show my pet segmentation percentages. "
            "Penilaian lama mungkin tidak mempunyai nilai tersebut."
        ),
        "zh": (
            "图像分割估计照片中与牙龈炎和牙结石相关的区域。"
            "它与分类热力图不同，会为这些区域预测分割掩膜。"
            "模型可能漏掉区域，也可能错误标出无关物体。"
            "面积百分比指上传照片中的像素比例，"
            "并非宠物整个口腔受影响的比例。"
            "分割掩膜用于辅助理解图像，并非精确的临床测量。"
            "如需查看已保存的数值，请选择宠物并询问："
            "Show my pet segmentation percentages。"
            "较早的评估可能没有保存这些数值。"
        ),
    },
    "explain_confidence": {
        "ms": (
            "Keyakinan pengelasan ialah skor model bagi sesuatu keadaan "
            "dalam imej ini. Ia bukan tahap keterukan penyakit dan "
            "tidak semestinya kebarangkalian yang telah ditentukur. "
            "Contohnya, skor 95% tidak bermaksud penyakit itu 95% teruk "
            "atau diagnosisnya pasti. Anggaran tahap keterukan ialah "
            "rujukan berasingan yang dijana sistem. Dapatan veterinar "
            "direkodkan secara berasingan."
        ),
        "zh": (
            "分类置信度是模型针对这张图像中某种状况给出的分数。"
            "它不代表疾病严重程度，也不一定是经过校准的概率。"
            "例如，95% 的分数不表示疾病有 95% 严重，"
            "也不代表诊断已经确定。"
            "估计严重程度是系统另外生成的参考结果，"
            "兽医检查结果则单独记录。"
        ),
    },
})

FAQ_TRANSLATIONS.update({
    "daily_dental_care": {
        "ms": (
            "Memberus gigi setiap hari disyorkan untuk penjagaan "
            "pencegahan apabila veterinar menganggapnya sesuai. "
            "Gunakan berus gigi haiwan yang lembut dan ubat gigi "
            "haiwan yang sesuai untuk spesiesnya. Perkenalkan "
            "memberus gigi secara beransur-ansur. Jika mulut sakit, "
            "meradang atau baru menerima rawatan, dapatkan nasihat "
            "veterinar sebelum memberus."
        ),
        "zh": (
            "在兽医认为适合的情况下，建议每天刷牙以预防牙齿问题。"
            "使用柔软的宠物牙刷，以及适合该物种的宠物牙膏，"
            "并逐步让宠物适应刷牙。如果口腔疼痛、发炎，"
            "或刚接受过治疗，请先咨询兽医再刷牙。"
        ),
    },
    "brushing_technique": {
        "ms": (
            "Mulakan secara beransur-ansur supaya haiwan selesa "
            "dengan sentuhan di sekitar mulut dan ubat gigi haiwan. "
            "Apabila haiwan boleh menerimanya, gunakan berus gigi "
            "haiwan yang lembut untuk membersihkan permukaan luar "
            "gigi dengan perlahan. Pastikan sesi tenang dan berikan "
            "ganjaran atas kerjasamanya. Jangan paksa mulut terbuka "
            "atau teruskan jika sakit. Minta veterinar menunjukkan "
            "teknik yang sesuai."
        ),
        "zh": (
            "逐步开始，让宠物先适应口腔周围的触碰和宠物牙膏。"
            "在宠物能够接受时，用柔软的宠物牙刷轻轻清洁牙齿外侧。"
            "保持过程平静，并奖励配合的行为。"
            "不要强行掰开嘴巴，也不要在宠物疼痛时继续。"
            "请兽医示范适合的刷牙方法。"
        ),
    },
    "bad_breath": {
        "ms": (
            "Bau mulut yang berterusan tidak patut diabaikan. "
            "Ia boleh berkaitan dengan penyakit pergigian atau "
            "masalah lain, jadi aturkan pemeriksaan veterinar. "
            "Chatbot atau foto tidak boleh menentukan puncanya. "
            "Produk penyegar nafas tidak menggantikan usaha "
            "mengenal pasti dan menangani masalah sebenar."
        ),
        "zh": (
            "持续口臭不应被忽视。它可能与牙齿疾病或其他问题有关，"
            "因此请安排兽医检查。聊天机器人或照片无法确定原因。"
            "清新口气的产品不能代替查明和处理根本问题。"
        ),
    },
    "dental_warning_signs": {
        "ms": (
            "Tanda amaran yang mungkin termasuk bau mulut berterusan, "
            "gusi merah atau bengkak, mendapan yang kelihatan, "
            "air liur berlebihan, kesukaran mengunyah atau perubahan "
            "tabiat makan. Tanda ini boleh mempunyai pelbagai punca "
            "dan memerlukan pemeriksaan veterinar. Foto yang kelihatan "
            "normal tidak menolak masalah di bawah garis gusi."
        ),
        "zh": (
            "可能的警示包括持续口臭、牙龈发红或肿胀、"
            "可见沉积物、流口水、咀嚼困难或进食行为改变。"
            "这些表现可能有不同原因，需要兽医检查。"
            "照片看起来正常，也不能排除牙龈线以下的问题。"
        ),
    },
})

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

    # Known navigation commands have explicit translations.
    control_translation = (
        CONVERSATION_TRANSLATIONS.get(intent, {}).get(language)
    )

    if control_translation and result.get("mode") == "rule":
        result["reply"] = control_translation
        return result

    # Preserve urgent, medication and other safety-rule replies.
    if result.get("mode") == "rule":
        return result

    if intent == "clarify":
        # Preserve the existing, more specific follow-up clarification.
        if result.get("reply") == FOLLOWUP_CLARIFICATION:
            result["reply"] = (
                FOLLOWUP_CLARIFICATION_TRANSLATIONS.get(
                    language, result["reply"]
                )
            )
            return result

        original_reply = result.get("reply", "")

        generic_fallback = (
            original_reply.startswith(
                "I’m not sure which question you mean."
            )
            or original_reply.startswith(
                "Could you describe what you need help with?"
            )
        )

        # Preserve specific errors and clarification instructions.
        if not generic_fallback:
            return result       

        has_choices = bool(result.get("suggested_questions"))

        translations = {
            "ms": (
                "Saya belum pasti maksud soalan ini. "
                "Pilih soalan cadangan atau nyatakan semula soalan anda."
                if has_choices else
                "Saya belum pasti maksud soalan ini. "
                "Adakah anda bertanya tentang penjagaan gigi, "
                "keputusan AI, rekod perubatan, janji temu atau produk?"
            ),
            "zh": (
                "我还不确定您的意思。请选择建议的问题，"
                "或换一种方式描述您的问题。"
                if has_choices else
                "我还不确定您的意思。您想询问牙齿护理、"
                "AI 结果、医疗记录、预约，还是产品？"
            ),
        }

        if language in translations:
            result["reply"] = translations[language]

        # Keep suggested questions and routing metadata intact.
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

def translate_product_explanation(explanation, language):
    if not explanation or language not in {"ms", "zh"}:
        return explanation

    translations = {
        (
            "Matched to your requested care purpose, "
            "not a confirmed diagnosis."
        ): (
            "Dipadankan dengan tujuan penjagaan yang anda minta, "
            "bukan diagnosis yang disahkan.",
            "根据您请求的护理用途匹配，并非依据确诊结果。",
        ),
        (
            "The consultation records plaque. Matching products "
            "are labelled for plaque control."
        ): (
            "Konsultasi merekodkan plak. Produk yang sepadan "
            "dilabelkan untuk kawalan plak.",
            "问诊记录中记有牙菌斑。匹配产品的标签用途为牙菌斑控制。",
        ),
        (
            "The consultation records gingivitis. Plaque-control "
            "products are shown as supportive home-care options, "
            "not as treatment for gum inflammation."
        ): (
            "Konsultasi merekodkan gingivitis. Produk kawalan plak "
            "dipaparkan sebagai sokongan penjagaan di rumah, "
            "bukan rawatan untuk keradangan gusi.",
            "问诊记录中记有牙龈炎。牙菌斑控制产品仅作为辅助居家护理选项，"
            "并非治疗牙龈炎症的产品。",
        ),
        (
            "The consultation records calculus or tartar. "
            "Plaque-control products are preventive care options; "
            "they are not presented as removing existing calculus."
        ): (
            "Konsultasi merekodkan karang gigi. Produk kawalan plak "
            "ialah pilihan penjagaan pencegahan dan tidak ditawarkan "
            "sebagai cara membuang karang gigi yang sedia ada.",
            "问诊记录中记有牙结石。牙菌斑控制产品用于预防性护理，"
            "不表示能够去除已有牙结石。",
        ),
        (
            "The consultation records a healthy or normal finding. "
            "Matching products support routine oral hygiene."
        ): (
            "Konsultasi merekodkan dapatan sihat atau normal. "
            "Produk yang sepadan menyokong kebersihan mulut rutin.",
            "问诊记录中记有健康或正常的检查发现。"
            "匹配产品用于支持日常口腔卫生。",
        ),
        (
            "The consultation records a routine dental-care visit. "
            "Matching products support routine oral hygiene; "
            "this does not establish healthy dentition or a vet's "
            "endorsement of a particular product."
        ): (
            "Konsultasi merekodkan lawatan penjagaan pergigian rutin. "
            "Produk yang sepadan menyokong kebersihan mulut rutin. "
            "Ini tidak mengesahkan gigi sihat atau bahawa veterinar "
            "menyokong produk tertentu.",
            "问诊记录中记有常规牙齿护理就诊。匹配产品用于日常口腔卫生，"
            "这不能证明牙齿健康，也不代表兽医认可某个具体产品。",
        ),
        (
            "The recorded home-care instructions were used "
            "to select the care purpose."
        ): (
            "Arahan penjagaan di rumah yang direkodkan digunakan "
            "untuk menentukan tujuan penjagaan.",
            "护理用途依据已记录的居家护理指示确定。",
        ),
    }

    # Translate only complete, recognized system messages.
    # Preserve the entire original explanation if anything is unknown.
    remaining = explanation.strip()
    translated = []
    index = 0 if language == "ms" else 1

    while remaining:
        for original, alternatives in translations.items():
            if remaining == original:
                translated.append(alternatives[index])
                remaining = ""
                break

            if remaining.startswith(original + " "):
                translated.append(alternatives[index])
                remaining = remaining[len(original):].strip()
                break
        else:
            return explanation

    return " ".join(translated)

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
        translated_explanation = translate_product_explanation(
            explanation, language
        )

        heading = (
            "Penjelasan padanan:"
            if language == "ms"
            else "匹配说明："
        )

        if translated_explanation == explanation:
            heading = text["explanation"][index]

        sections.append(
            heading + "\n" + translated_explanation
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