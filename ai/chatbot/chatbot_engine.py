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


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("’", "'").replace("can't", "cannot")

    return " ".join(
        re.findall(r"[a-z0-9]+", text)
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
        urgent_phrases = (
            "cannot breathe",
            "difficulty breathing",
            "struggling to breathe",
            "uncontrolled bleeding",
            "bleeding will not stop",
            "unconscious",
        )

        if any(
            re.search(
                r"\b" + re.escape(phrase) + r"\b",
                text,
            )
            for phrase in urgent_phrases
        ):
            return response(
                intent="urgent_vet_contact",
                reply=(
                    "If your pet is currently struggling to breathe, "
                    "unconscious, or has uncontrolled bleeding, "
                    "contact a veterinarian or emergency veterinary "
                    "clinic immediately. Do not wait for this chatbot "
                    "or an online photo review. I cannot assess an "
                    "emergency through chat."
                ),
                mode="rule",
                sources=[
                    "https://avma.org/resources/pet-owners/"
                    "emergencycare/13-animal-emergencies-require-"
                    "immediate-veterinary-consultation-andor-care"
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
        query = self.vector(features(message))

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