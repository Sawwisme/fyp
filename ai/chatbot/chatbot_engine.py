import math
import re
import unicodedata
from collections import Counter

from chatbot_knowledge import KNOWLEDGE


STOP_WORDS = {
    "a", "an", "the", "is", "are", "what", "how",
    "do", "does", "i", "my", "can", "you", "please",
    "to", "of", "for", "it", "in", "on", "with", "about",
}

STOP_WORDS.update({
    "me", "tell", "has", "have", "had",
    "be", "been", "being", "was", "were", "am",
    "and", "or", "but",
    "this", "that", "these", "those",
    "its", "their", "our", "your",
    "we", "us", "he", "she", "they", "his", "her",
    "pet", "pets", "cat", "cats", "dog", "dogs",
    "should", "could", "would", "will", "need", "needs",
})

STOP_WORDS.update({
    "show",
    "view",
    "recorded",
    "display",
})


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("’", "'").replace("can't", "cannot")

    text = " ".join(
        re.findall(r"[a-z0-9]+", text)
    )

    phrase_aliases = {
        "stinky mouth": "bad breath",
        "smelly mouth": "bad breath",
        "tooth disease": "dental disease",
    }

    for original, replacement in phrase_aliases.items():
        text = text.replace(original, replacement)

    word_aliases = {
        "teeth": "tooth",
        "brushing": "brush",
        "brushed": "brush",
        "brushes": "brush",
        "kitten": "cat",
        "kittens": "cat",
        "puppy": "dog",
        "puppies": "dog",
        "symptoms": "signs",
        "symptom": "signs",
        "followup": "follow up",
        "prescriptions": "prescription",
        "earlier": "previous",
        "scans": "scan",
        "results": "result",
    }

    return " ".join(
        word_aliases.get(word, word)
        for word in text.split()
    )


def features(text):
    words = [
        word
        for word in normalize(text).split()
        if word not in STOP_WORDS
    ]

    bigrams = [
        f"{first} {second}"
        for first, second in zip(words, words[1:])
    ]

    return Counter(words + bigrams)


def response(
    intent,
    reply,
    mode,
    sources=None,
    similarity=None,
):
    return {
        "intent": intent,
        "reply": reply,
        "mode": mode,
        "sources": sources or [],
        "similarity": similarity,
    }

def detect_specific_intent(text):
    words = set(text.split())

    prescription_lookup = (
        "prescription" in words
        and bool(words & {
            "show", "view", "recorded", "prescribed",
            "last", "latest", "instructions", "history",
            "visit", "consultation",
        })
        and not bool(words & {
            "buy", "shop", "purchase",
            "product", "products", "toothpaste",
        })
    )

    if prescription_lookup:
        return "recorded_prescriptions"

    comparison_question = bool(words & {
        "compare", "compared", "comparing", "comparison",
    })

    analysis_topic = bool(words & {
        "scan", "analysis", "assessment", "result", "severity",
    })

    time_reference = bool(words & {
        "previous", "latest", "last", "before",
        "progress", "changed", "improved",
    })

    if comparison_question and analysis_topic and time_reference:
        return "compare_analysis_progress"

    dental_brushing = (
        "brush" in words
        and bool(words & {
            "tooth", "dental", "oral", "mouth",
        })
    )

    frequency_question = bool(re.search(
        r"\bhow (?:often|frequently|many times)\b"
        r"|\bdaily\b"
        r"|\bevery day\b",
        text,
    ))

    if dental_brushing and frequency_question:
        return "daily_dental_care"

    next_step_question = bool(re.search(
        r"\bwhat (?:should|can) (?:i|we) do\b"
        r"|\bwhat do (?:i|we) do\b",
        text,
    ))

    if next_step_question and analysis_topic:
        return "pet_next_steps"

    return None


class HybridChatbot:
    def __init__(self):
        documents = [
            (entry, features(question))
            for entry in KNOWLEDGE
            for question in entry["questions"]
        ]

        if not documents:
            raise ValueError("The chatbot knowledge base is empty.")

        frequencies = Counter()

        for _, terms in documents:
            frequencies.update(terms.keys())

        # Smoothed inverse document frequency.
        self.idf = {
            term: (
                math.log(
                    (1 + len(documents)) / (1 + count)
                ) + 1
            )
            for term, count in frequencies.items()
        }

        self.documents = [
            (entry, self.vector(terms))
            for entry, terms in documents
        ]

    def vector(self, terms):
        vector = {
            term: (
                1 + math.log(count)
            ) * self.idf[term]
            for term, count in terms.items()
            if term in self.idf
        }

        length = math.sqrt(
            sum(value * value for value in vector.values())
        )

        if not length:
            return {}

        return {
            term: value / length
            for term, value in vector.items()
        }

    def answer(self, message):
        if (
            not isinstance(message, str)
            or not 1 <= len(message.strip()) <= 2000
        ):
            raise ValueError(
                "Enter a message between 1 and 2000 characters."
            )

        text = normalize(message)
        words = set(text.split())

# Rules take priority over NLP retrieval.
        emergency_phrases = (
            "cannot breathe",
            "difficulty breathing",
            "trouble breathing",
            "struggling to breathe",
            "not breathing",
            "uncontrolled bleeding",
            "heavy bleeding",
            "bleeding heavily",
            "severe bleeding",
            "excessive bleeding",
            "continuous bleeding",
            "continuous oral bleeding",
            "bleeding will not stop",
            "bleeding won t stop",
            "bleeding does not stop",
            "unconscious",
            "unresponsive",
            "collapsed",
            "collapse",
            "facial swelling",
            "swollen face",
            "face is swollen",
            "severe pain",
            "extreme pain",
        )

        prompt_assessment_phrases = (
            "unable to eat",
            "cannot eat",
            "not eating",
            "stopped eating",
            "unable to drink",
            "cannot drink",
            "not drinking",
            "stopped drinking",
            "severe swelling",
            "pus",
            "broken tooth",
            "fractured tooth",
        )

        def contains_phrase(phrases):
            return any(
                re.search(
                    r"\b" + re.escape(phrase) + r"\b",
                    text,
                )
                for phrase in phrases
            )

        if contains_phrase(emergency_phrases):
            return response(
                intent="urgent_vet_contact",
                reply=(
                    "If these symptoms are happening now, contact "
                    "a veterinarian or emergency veterinary clinic "
                    "immediately for assessment and instructions. "
                    "Do not wait for an AI scan, an online photo "
                    "review or a routine booking. This chatbot "
                    "cannot determine the cause or assess an "
                    "emergency remotely."
                ),
                mode="rule",
                sources=[
                    "https://www.vet.cornell.edu/hospitals/"
                    "services/emergency-and-critical-care-0"
                ],
            )

        if contains_phrase(prompt_assessment_phrases):
            return response(
                intent="urgent_vet_contact",
                reply=(
                    "If your pet is currently experiencing these "
                    "symptoms, contact your veterinarian promptly "
                    "for advice on how urgently an examination "
                    "is needed. Do not rely on the AI severity "
                    "estimate to decide it is safe to wait. "
                    "If there is breathing difficulty, collapse, "
                    "severe pain or uncontrolled bleeding, seek "
                    "emergency veterinary care immediately."
                ),
                mode="rule",
                sources=[
                    "https://www.vet.cornell.edu/hospitals/"
                    "services/emergency-and-critical-care-0"
                ],
            )

        if (
            "toothpaste" in words
            and words & {
                "human",
                "humans",
                "people",
                "adult",
                "adults",
            }
        ):
            return response(
                intent="human_toothpaste_warning",
                reply=(
                    "Do not use human toothpaste for your cat or dog. "
                    "Choose toothpaste specifically intended for "
                    "the animal's species and follow your vet's "
                    "instructions. If your pet has swallowed human "
                    "toothpaste, contact your veterinarian with "
                    "the product details and estimated amount."
                ),
                mode="rule",
                sources=[
                    "https://www.aaha.org/resources/"
                    "your-pets-dental-care/"
                ],
            )

        medication_words = {
            "dose",
            "dosage",
            "mg",
            "ibuprofen",
            "paracetamol",
            "antibiotics",
        }

        if words & medication_words:
            return response(
                intent="medication_referral",
                reply=(
                    "I cannot prescribe medicines or calculate a "
                    "dose for your pet. Contact your veterinarian "
                    "for advice specific to your pet. If your pet "
                    "may have swallowed a medicine accidentally, "
                    "contact a veterinarian promptly."
                ),
                mode="rule",
            )

        if text in {
            "hi",
            "hello",
            "hey",
            "good morning",
            "good evening",
        }:
            return response(
                intent="greeting",
                reply=(
                    "Hello! I can explain common pet dental terms "
                    "and help with VetDental assessments, "
                    "appointments and follow-up updates. "
                    "What would you like help with?"
                ),
                mode="rule",
            )

        if text in {
            "thanks",
            "thank you",
            "bye",
            "goodbye",
        }:
            return response(
                intent="courtesy",
                reply=(
                    "You're welcome. You can ask another pet "
                    "dental or VetDental question whenever you need."
                ),
                mode="rule",
            )

        # NLP: TF-IDF vectors and cosine similarity.
        terms = features(message)

        content_words = {
            term
            for term in terms
            if " " not in term
        }

        known_words = {
            word
            for word in content_words
            if word in self.idf
        }

        coverage = (
            len(known_words) / len(content_words)
            if content_words
            else 0.0
        )

        if coverage < 0.5:
            return response(
                intent="clarify",
                reply=(
                    "I could not match that to a supported topic. "
                    "You can ask about pet dental care, AI results, "
                    "appointments, follow-up care or clinic products. "
                    "Please rephrase your question."
                ),
                mode="fallback",
            )

        specific_intent = detect_specific_intent(text)

        if specific_intent is not None:
            entry = next(
                (
                    item
                    for item in KNOWLEDGE
                    if item["intent"] == specific_intent
                ),
                None,
            )

            if entry is not None:
                return response(
                    intent=specific_intent,
                    reply=entry["reply"],
                    mode="rule",
                    sources=entry["sources"],
                )

        query = self.vector(terms)

        ranked = {}
        entries = {}

        for entry, vector in self.documents:
            score = sum(
                value * vector.get(term, 0.0)
                for term, value in query.items()
            )

            intent = entry["intent"]

            ranked[intent] = max(
                ranked.get(intent, 0.0),
                score,
            )

            entries[intent] = entry

        ranking = sorted(
            ranked.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        intent, best = ranking[0]

        runner_up = (
            ranking[1][1]
            if len(ranking) > 1
            else 0.0
        )

        # Initial thresholds, to be evaluated with test questions.
        if best < 0.30 or best - runner_up < 0.05:
            return response(
                intent="clarify",
                reply=(
                    "I could not confidently match that question. "
                    "Please ask one question about plaque, calculus, "
                    "gingivitis, AI results, vet reviews, booking, "
                    "cancellation or follow-up photos. For symptoms "
                    "or treatment decisions, contact your veterinarian."
                ),
                mode="fallback",
            )

        entry = entries[intent]

        return response(
            intent=intent,
            reply=entry["reply"],
            mode="nlp",
            sources=entry["sources"],
            similarity=round(best, 4),
        )


chatbot = HybridChatbot()