from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ChatbotMessage(Base):
    __tablename__ = "chatbot_messages"

    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "sender_type",
            "client_request_id",
            name="uq_chat_message_request",
        ),
        Index(
            "ix_chat_message_conversation_id",
            "conversation_id",
            "message_id",
        ),
    )

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

    client_request_id = Column(
        String(36),
        nullable=True,
    )

    response_metadata = Column(
        JSON,
        nullable=True,
    )

    sent_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    conversation = relationship(
        "ChatbotConversation",
        back_populates="messages",
    )