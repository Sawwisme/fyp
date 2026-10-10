from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import relationship

from app.database import Base


class ChatbotConversation(Base):
    __tablename__ = "chatbot_conversations"

    conversation_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )
    pet_id = Column(
        Integer,
        ForeignKey("pets.pet_id"),
        nullable=True,
    )
    started_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)

    user = relationship("User")
    pet = relationship("Pet")
    messages = relationship(
        "ChatbotMessage",
        back_populates="conversation",
        order_by="ChatbotMessage.message_id",
    )