from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
import enum

from app.database import Base


class MessageDirection(str, enum.Enum):
    incoming = "incoming"
    outgoing = "outgoing"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    recipient = Column(String, index=True, nullable=False)
    sender = Column(String, nullable=False)
    message_text = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    direction = Column(Enum(MessageDirection), nullable=False)

    def __repr__(self):
        return f"<Message(id={self.id}, recipient={self.recipient}, direction={self.direction})>"

