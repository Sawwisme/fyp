"""Phrase-based multilingual triage, not diagnosis or a general translator."""
import re
import unicodedata


PHRASES = {
    "emergency": {
        "zh": (
            "呼吸困难", "呼吸困難", "无法呼吸", "無法呼吸", "不能呼吸",
            "没有呼吸", "沒有呼吸", "停止呼吸", "喘不过气", "喘不過氣",
            "出血不止", "血流不止", "大量出血", "失去意识", "失去意識",
            "昏迷", "没有反应", "沒有反應", "脸肿", "臉腫", "面部肿胀",
            "剧痛", "劇痛",
        ),
        "ms": (
            "susah bernafas", "sukar bernafas", "kesukaran bernafas",
            "tidak boleh bernafas", "tak boleh bernafas", "tidak bernafas",
            "pendarahan tidak berhenti", "darah tak berhenti", "pendarahan teruk",
            "darah banyak", "tidak sedarkan diri", "tak sedarkan diri",
            "pengsan", "muka bengkak", "sakit teruk", "sakit sangat",
        ),
        "en": (
            "cannot breathe", "can't breathe", "cant breathe", "difficulty breathing",
            "trouble breathing", "struggling to breathe", "not breathing",
            "uncontrolled bleeding", "heavy bleeding", "bleeding heavily",
            "severe bleeding", "excessive bleeding", "continuous bleeding",
            "continuous oral bleeding", "bleeding will not stop", "bleeding won't stop",
            "bleeding does not stop", "unconscious", "unresponsive", "collapsed",
            "collapse", "facial swelling", "swollen face", "face is swollen",
            "severe pain", "extreme pain",
        ),
    },
    "prompt": {
        "zh": (
            "不吃东西", "不吃東西", "不吃饭", "不吃飯", "无法进食", "無法進食",
            "不能吃东西", "不能吃東西", "不喝水", "牙齿断了", "牙齒斷了",
            "断牙", "斷牙", "流脓", "流膿", "化脓", "化膿",
        ),
        "ms": (
            "tak nak makan", "tidak mahu makan", "tak mahu makan", "tidak makan",
            "tak makan", "tak boleh makan", "tidak boleh makan", "tidak minum",
            "tak minum", "tidak mahu minum", "tak mahu minum", "gigi patah",
            "bernanah", "bengkak teruk",
        ),
        "en": (
            "unable to eat", "cannot eat", "not eating", "stopped eating",
            "unable to drink", "cannot drink", "not drinking", "stopped drinking",
            "severe swelling", "pus", "broken tooth", "fractured tooth",
        ),
    },
}

REPLIES = {
    "emergency": {
        "en": (
            "If these symptoms are happening now, contact a veterinarian or emergency "
            "veterinary clinic immediately for assessment and instructions. Do not wait "
            "for an AI scan, online review or routine booking. This chatbot cannot "
            "determine the cause or assess an emergency remotely."
        ),
        "ms": (
            "Jika gejala ini sedang berlaku, hubungi doktor veterinar atau klinik "
            "kecemasan veterinar dengan segera untuk pemeriksaan dan arahan. Jangan "
            "tunggu imbasan AI, semakan dalam talian atau tempahan biasa. Chatbot ini "
            "tidak boleh menentukan punca atau menilai kecemasan dari jauh."
        ),
        "zh": (
            "如果这些症状正在发生，请立即联系兽医或兽医急诊，获取检查和处理指示。"
            "不要等待AI扫描、线上审核或普通预约。聊天机器人无法远程确定病因或评估急症。"
        ),
    },
    "prompt": {
        "en": (
            "If your pet currently has these symptoms, contact your veterinarian promptly "
            "for advice on how urgently an examination is needed. Do not use the AI "
            "severity estimate to decide it is safe to wait. If breathing difficulty, "
            "collapse, severe pain or uncontrolled bleeding occurs, seek emergency "
            "veterinary care immediately."
        ),
        "ms": (
            "Jika haiwan anda sedang mengalami gejala ini, hubungi doktor veterinar "
            "secepat mungkin untuk menentukan keperluan pemeriksaan. Jangan gunakan "
            "anggaran keterukan AI untuk memutuskan bahawa selamat untuk menunggu. "
            "Jika terdapat kesukaran bernafas, rebah, kesakitan teruk atau pendarahan "
            "tidak terkawal, dapatkan rawatan kecemasan veterinar dengan segera."
        ),
        "zh": (
            "如果宠物目前出现这些症状，请尽快联系兽医，询问需要多快接受检查。"
            "不要依靠AI严重程度估计来决定是否可以等待。若出现呼吸困难、倒地、"
            "剧痛或出血不止，请立即寻求兽医急诊。"
        ),
    },
}


def _matches(text, phrase, language):
    pattern = re.escape(phrase)
    if phrase in {"没有呼吸", "沒有呼吸"}:
        pattern += r"(?!\s*(?:困难|困難))"
    if language != "zh":
        pattern = r"(?<!\w)" + pattern + r"(?!\w)"
    return re.finditer(pattern, text)


def _explicitly_negated(text, match, language):
    prefix = text[max(0, match.start() - 55):match.start()]
    if language == "zh":
        # Do not confuse a negation inside a symptom phrase, e.g.
        # 无法呼吸 / 没有呼吸, with denial of the whole symptom.
        if re.search(r"(?:并非|並非|不是|并不是|並不是)(?:没有|沒有|无|無)\s*$", prefix):
            return False
        return bool(re.search(r"(?:没有|沒有|并无|並無|无|無|不是|否认|否認)\s*$", prefix))
    return bool(re.search(
        r"\b(?:no|not|without|denies|tidak|tak|tiada|bukan|tanpa|tidak ada|tak ada)\s*$",
        prefix,
    ))


def multilingual_safety_reply(message, preferred_language="en"):
    text = unicodedata.normalize("NFKC", str(message)).casefold()
    text = text.replace("’", "'")
    text = " ".join(text.split())

    # Emergency cues always outrank prompt-assessment cues in mixed messages.
    for urgency in ("emergency", "prompt"):
        found = []
        for language, phrases in PHRASES[urgency].items():
            for phrase in phrases:
                for match in _matches(text, phrase, language):
                    if not _explicitly_negated(text, match, language):
                        found.append(language)
        if not found:
            continue

        language = (
            "zh" if "zh" in found else "ms" if "ms" in found
            else preferred_language if preferred_language in {"en", "ms", "zh"}
            else "en"
        )
        return {
            "intent": "urgent_vet_contact",
            "reply": REPLIES[urgency][language],
            "mode": "rule",
            "sources": [
                "https://www.vet.cornell.edu/hospitals/services/emergency-and-critical-care-0"
            ],
            "similarity": None,
            "products": [],
            "suggested_questions": [],
            "recommended_action": "NONE",
            "language": language,
            "urgency_level": urgency,
        }
    return None
