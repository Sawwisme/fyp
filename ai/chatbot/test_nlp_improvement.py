from chatbot_engine import chatbot, normalize

questions = [
    "What is gingivtis?",
    "What is tartar?",
    "My dog has smelly breath",
    "How often should I brush my cat's teeth?",
    "Show my latest scan outcome",
    "Show my prev assessment",
    "I wanna book an appoinment",
    "Can I see my prescripton?",
    "My dog cannot breathe",
    "Can I use human toothpaste?",
    "What is the weather today?",
    "How to repair my laptop?",
]

for question in questions:
    answer = chatbot.answer(question)

    print("=" * 65)
    print("Question:", question)
    print("Normalized:", normalize(question))
    print("Intent:", answer["intent"])
    print("Mode:", answer["mode"])
    print("Similarity:", answer.get("similarity"))
    print("NLP metrics:", answer.get("nlp_metrics"))
    print("Reply:", answer["reply"])