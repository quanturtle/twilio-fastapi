from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class MessageDirection(str, enum.Enum):
    incoming = "incoming"
    outgoing = "outgoing"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    openai_conversation_id = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to messages
    messages = relationship("Message", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, first_name={self.first_name}, last_name={self.last_name}, phone_number={self.phone_number})>"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    recipient = Column(String, index=True, nullable=False)
    sender = Column(String, nullable=False)
    message_text = Column(String, nullable=False)
    timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    direction = Column(Enum(MessageDirection), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationship to user
    user = relationship("User", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, recipient={self.recipient}, direction={self.direction})>"
