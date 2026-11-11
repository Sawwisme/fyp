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

KNOWLEDGE.extend([
    {
        "intent": "explain_latest_analysis",
        "questions": [
            "explain my latest result",
            "what does my pet result mean",
            "show my latest dental analysis",
            "how is my pet dental condition",
            "what conditions were detected in my scan",
        ],
        "reply": (
            "Select a pet so I can explain its latest "
            "completed dental assessment."
        ),
        "sources": [],
    },
    {
        "intent": "explain_pet_severity",
        "questions": [
            "how severe is my pet condition",
            "what is my pet estimated severity",
            "what severity did my latest analysis show",
            "is my pet result mild moderate or severe",
        ],
        "reply": (
            "Select a pet so I can check its recorded "
            "system-estimated severity."
        ),
        "sources": [],
    },
    {
        "intent": "dental_analysis_history",
        "questions": [
            "show my pet previous results",
            "what was the previous dental analysis",
            "when was my pet last analysis",
            "show my dental scan history",
        ],
        "reply": (
            "Select a pet so I can check its completed "
            "dental assessment history."
        ),
        "sources": [],
    },
    {
        "intent": "compare_analysis_progress",
        "questions": [
            "has my pet improved",
            "compare with the previous result",
            "is my pet severity getting worse",
            "has the estimated severity changed",
            "compare my last two scans",
        ],
        "reply": (
            "Select a pet so I can compare its latest "
            "two completed assessments."
        ),
        "sources": [],
    },
])

KNOWLEDGE.extend([
    {
        "intent": "explain_gradcam",
        "questions": [
            "what does the heatmap mean",
            "explain gradcam",
            "what do the red areas on the heatmap show",
            "why is the heatmap red",
            "what do the disease boxes mean",
            "does the heatmap show the exact disease area",
        ],
        "reply": (
            "The heatmap shows which image regions influenced "
            "the AI classification most strongly. Warmer colours "
            "show stronger relative attention. The labelled boxes "
            "identify attention regions associated with a prediction; "
            "they are not confirmed disease boundaries. "
            "Red does not mean severe disease, and the heatmap "
            "cannot measure how much of your pet's mouth is affected."
        ),
        "sources": [],
    },
    {
        "intent": "explain_segmentation",
        "questions": [
            "what does segmentation mean",
            "explain the segmentation result",
            "what are the coloured masks",
            "what does the affected area percentage mean",
            "does segmentation measure the whole mouth",
            "difference between segmentation and heatmap",
        ],
        "reply": (
            "Segmentation estimates image regions associated with "
            "gingivitis and calculus. Unlike the classification "
            "heatmap, it predicts a mask for those regions. "
            "It can miss areas or highlight unrelated objects. "
            "An area percentage refers to pixels in the submitted "
            "image, not the percentage of your pet's mouth affected. "
            "The masks support image interpretation and are not "
            "precise clinical measurements. "
            "For saved measurements, select a pet and ask "
            "Show my pet segmentation percentages. "
            "Older assessments may not contain these values."
        ),
        "sources": [],
    },
    {
        "intent": "explain_confidence",
        "questions": [
            "what is classification confidence",
            "what does the confidence percentage mean",
            "is confidence the same as severity",
            "does a model score prove disease",
            "what does 95 percent confidence mean",
        ],
        "reply": (
            "Classification confidence is the model's score for "
            "a condition in this image. It is not disease severity "
            "and is not necessarily a calibrated probability. "
            "For example, a 95% score does not mean the condition "
            "is 95% severe or that the diagnosis is certain. "
            "Estimated Severity is a separate system-generated "
            "reference, while veterinary findings are recorded "
            "separately."
        ),
        "sources": [],
    },
])

KNOWLEDGE.extend([
    {
        "intent": "upcoming_appointment",
        "questions": [
            "do I have an appointment",
            "when is my next appointment",
            "show my upcoming appointments",
            "which vet did I select",
            "which clinic is my appointment at",
            "where is my booked clinic",
            "what is my upcoming appointment status",
        ],
        "reply": (
            "Select a pet so I can check its upcoming appointments."
        ),
        "sources": [],
    },
])

KNOWLEDGE.extend([
    {
        "intent": "my_followup_care",
        "questions": [
            "show my pet follow up instructions",
            "what did the vet ask me to do",
            "does my pet need follow up care",
            "do I need to submit photos",
            "can I submit another photo",
            "is my follow up awaiting review",
            "what is my follow up status",
        ],
        "reply": (
            "Select a pet so I can check its recorded "
            "follow-up instructions."
        ),
        "sources": [],
    },
])

KNOWLEDGE.extend([
    {
        "intent": "pet_next_steps",
        "questions": [
            "what should I do next",
            "what should I do about my pet result",
            "should I see a vet",
            "does my pet need a dental appointment",
            "what action should I take after the scan",
        ],
        "reply": (
            "Select a pet so I can check its latest "
            "assessment and recorded veterinary feedback."
        ),
        "sources": [],
    },
])

KNOWLEDGE.extend([
    {
        "intent": "product_recommendation",
        "questions": [
            "recommend dental care products",
            "what dental products are available",
            "show products for my pet teeth",
            "where can I buy pet toothpaste",
            "show available toothbrushes and dental products",
        ],
        "reply": (
            "I can show available dental-care products. "
            "Product availability does not establish "
            "suitability for your pet."
        ),
        "sources": [],
    },
])

KNOWLEDGE.extend([
    {
        "intent": "daily_dental_care",
        "questions": [
            "how often should I brush my dog teeth",
            "how often should I brush my cat teeth",
            "should I brush every day",
            "how frequently should I clean pet teeth",
            "what is a daily dental routine",
        ],
        "reply": (
            "Daily toothbrushing is recommended for preventive "
            "dental care when your vet considers it appropriate. "
            "Use a soft pet toothbrush and species-appropriate "
            "pet toothpaste. Introduce brushing gradually. "
            "If the mouth is painful, inflamed or recently treated, "
            "ask your vet before brushing."
        ),
        "sources": [
            "https://www.vet.cornell.edu/departments-centers-and-"
            "institutes/riney-canine-health-center/canine-health-"
            "information/periodontal-disease",
            "https://www.vet.cornell.edu/departments-centers-and-"
            "institutes/cornell-feline-health-center/health-information/"
            "feline-health-topics/feline-dental-disease",
        ],
    },
    {
        "intent": "brushing_technique",
        "questions": [
            "how do I clean my cat teeth",
            "how do I clean my dog teeth",
            "how do I brush pet teeth",
            "how should I introduce a toothbrush",
            "my pet does not like brushing",
        ],
        "reply": (
            "Start gradually, allowing your pet to become comfortable "
            "with handling around the mouth and pet toothpaste. "
            "Use a soft pet toothbrush to gently clean the outer "
            "tooth surfaces when your pet tolerates it. Keep sessions "
            "calm and reward cooperation. Do not force the mouth "
            "open or continue through pain. Ask your vet to "
            "demonstrate a suitable technique."
        ),
        "sources": [
            "https://www.vet.cornell.edu/about-us/news/"
            "20180221/veterinary-tips-pet-dental-care",
        ],
    },
    {
        "intent": "bad_breath",
        "questions": [
            "is bad breath normal",
            "why does my dog breath smell",
            "why does my cat have bad breath",
            "my pet has smelly breath",
            "should I worry about persistent bad breath",
        ],
        "reply": (
            "Persistent bad breath should not simply be dismissed. "
            "It can be associated with dental disease or other "
            "problems, so arrange a veterinary assessment. "
            "A chatbot or image cannot establish the cause. "
            "Breath-freshening products do not replace finding "
            "and addressing the underlying problem."
        ),
        "sources": [
            "https://www.vet.cornell.edu/departments-centers-and-"
            "institutes/riney-canine-health-center/canine-health-"
            "information/dental-disease-and-home-dental-care",
        ],
    },
    {
        "intent": "dental_warning_signs",
        "questions": [
            "what are signs of dental problems",
            "how can I notice dental disease",
            "what symptoms should I watch for",
            "what are common dental warning signs",
            "how do I know my pet needs a dental check",
        ],
        "reply": (
            "Possible warning signs include persistent bad breath, "
            "red or swollen gums, visible deposits, drooling, "
            "difficulty chewing or changes in eating behaviour. "
            "These signs have different possible causes and "
            "need veterinary assessment. A normal-looking photo "
            "does not rule out problems below the gumline."
        ),
        "sources": [
            "https://www.vet.cornell.edu/departments-centers-and-"
            "institutes/riney-canine-health-center/canine-health-"
            "information/dental-disease-and-home-dental-care",
        ],
    },
])

KNOWLEDGE.extend([
    {
        "intent": "pet_medical_history",
        "questions": [
            "show my pet medical history",
            "show previous completed consultations",
            "what did the vet diagnose",
            "show recorded diagnoses and treatments",
            "what happened at my pet last consultation",
        ],
        "reply": (
            "Select a pet so I can check its completed "
            "consultation records."
        ),
        "sources": [],
    },
    {
        "intent": "recorded_prescriptions",
        "questions": [
            "show my pet recorded prescriptions",
            "what medicines did the vet prescribe",
            "show prescription instructions from the last consultation",
            "what was prescribed at the latest visit",
            "show my pet prescription record",
        ],
        "reply": (
            "Select a pet so I can show prescriptions "
            "recorded at its latest completed consultation."
        ),
        "sources": [],
    },
])

KNOWLEDGE.extend([
    {
        "intent": "pet_segmentation_values",
        "questions": [
            "show my pet segmentation percentages",
            "what are my latest segmentation measurements",
            "how much of my image was marked",
            "show gingivitis and calculus area estimates",
        ],
        "reply": (
            "Select a pet so I can check its saved "
            "segmentation measurements."
        ),
        "sources": [],
    },
])

KNOWLEDGE.extend([
    {
        "intent": "pet_prediction_scores",
        "questions": [
            "show my pet classification scores",
            "what scores did my latest scan produce",
            "show confidence scores for my pet assessment",
            "what is the gingivitis score in my latest scan",
            "show the model scores from my dental result",
        ],
        "reply": (
            "Select a pet so I can check the classification "
            "scores saved with its latest assessment."
        ),
        "sources": [],
    },
])