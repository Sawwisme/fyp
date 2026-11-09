KNOWLEDGE = [
    {
        "intent": "plaque_information",
        "questions": [
            "what is dental plaque",
            "explain plaque on pet teeth",
            "what is the soft film on teeth",
        ],
        "reply": (
            "Dental plaque is a film of bacteria on teeth. "
            "When it accumulates, it can irritate the gums and "
            "contribute to periodontal disease. This explanation "
            "cannot confirm whether your pet has plaque; "
            "a vet can assess their mouth."
        ),
        "sources": [
            "https://vohc.org/how-periodontal-disease-develops/"
        ],
    },
    {
        "intent": "calculus_information",
        "questions": [
            "what is calculus",
            "what is tartar on teeth",
            "explain hard dental deposits",
            "difference between plaque and tartar",
        ],
        "reply": (
            "Dental calculus, also called tartar, is hardened plaque "
            "containing mineral deposits from saliva. It differs "
            "from the softer plaque film. Ask your vet about "
            "appropriate assessment and cleaning for your pet."
        ),
        "sources": [
            "https://vohc.org/how-periodontal-disease-develops/"
        ],
    },
    {
        "intent": "gingivitis_information",
        "questions": [
            "what is gingivitis",
            "explain inflamed gums",
            "what does gum inflammation mean",
            "why are gums red",
        ],
        "reply": (
            "Gingivitis means inflammation of the gums. Redness, "
            "swelling or bleeding can occur, but a photo or chatbot "
            "cannot establish the cause. Arrange a veterinary "
            "assessment if you notice changes in your pet's gums."
        ),
        "sources": [
            "https://www.vet.cornell.edu/departments-centers-and-institutes/"
            "cornell-feline-health-center/health-information/"
            "feline-health-topics/feline-dental-disease"
        ],
    },
    {
        "intent": "ai_interpretation",
        "questions": [
            "is the ai scan a diagnosis",
            "can i trust the ai result",
            "what does severe ai mean",
            "what does the scan score mean",
            "does high confidence mean severe disease",
        ],
        "reply": (
            "VetDental's AI results are screening references, "
            "not confirmed diagnoses. Model scores are not disease "
            "severity measurements. If a result concerns you, use "
            "Request vet review on the completed assessment or "
            "arrange a consultation. The reviewing vet's feedback "
            "is shown separately from the original AI result."
        ),
        "sources": [],
    },
    {
        "intent": "request_review",
        "questions": [
            "how do i request a vet review",
            "send my scan to a veterinarian",
            "share my assessment with a clinic",
            "where can i read vet feedback",
        ],
        "reply": (
            "On a completed AI assessment, choose Request vet review, "
            "select a clinic, and confirm Share assessment & request "
            "review. To check feedback later, open My vet reviews & "
            "feedback in AI Scan. Sharing a review request does not "
            "book an appointment."
        ),
        "sources": [],
    },
    {
        "intent": "book_appointment",
        "questions": [
            "how do i book an appointment",
            "make a dental appointment",
            "choose a vet and appointment time",
            "schedule a clinic visit",
        ],
        "reply": (
            "Open Booking, choose a clinic, and select your pet, "
            "an available vet, date and time. Review the details "
            "and any required deposit before confirming. If a vet "
            "review recommends a visit, Choose appointment time "
            "opens booking at the reviewing clinic."
        ),
        "sources": [],
    },
    {
        "intent": "cancel_appointment",
        "questions": [
            "how do i cancel an appointment",
            "cancel my booking",
            "remove a booked appointment",
        ],
        "reply": (
            "Open Booking and the appointment you want to manage, "
            "then use its cancellation action when available. "
            "The server checks whether it can still be cancelled. "
            "I cannot cancel appointments or confirm refund "
            "eligibility from this chat; read the appointment "
            "and payment details."
        ),
        "sources": [],
    },
    {
        "intent": "followup_update",
        "questions": [
            "how do i send follow up photos",
            "upload a recovery picture",
            "where is follow up care",
            "send progress update to vet",
        ],
        "reply": (
            "Open Follow-up Care from Booking and select the "
            "relevant task. Read the vet's instructions and submit "
            "photos or an update when the task allows it. After "
            "submission, check the task for feedback. Another "
            "submission may require the vet to request an "
            "additional update."
        ),
        "sources": [],
    },
]