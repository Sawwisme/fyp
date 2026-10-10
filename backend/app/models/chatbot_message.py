from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import relationship

from app.database import Base


class ChatbotMessage(Base):
    __tablename__ = "chatbot_messages"

    message_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    conversation_id = Column(
        Integer,
        ForeignKey("chatbot_conversations.conversation_id"),
        nullable=False,
    )
    sender_type = Column(String(20), nullable=False)
    message_text = Column(Text, nullable=False)
    sent_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    conversation = relationship(
        "ChatbotConversation",
        back_populates="messages",
    )