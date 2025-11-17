import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from openai import OpenAI
from dotenv import load_dotenv

from app.models.base import Base
from app.models.database import User, Message, MessageDirection

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/twilio_db"
)

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency to get database session. For FastAPI endpoints that use Depends(get_db)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for database sessions in background tasks."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize database tables
def init_db():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


def validate_phone_number(phone: str) -> str:
    """
    Validate and normalize phone number.
    For Paraguayan numbers: +595 followed by 9 digits (13 chars total).
    """
    normalized = phone.replace("whatsapp:", "").strip()

    # Remove all spaces
    normalized = normalized.replace(" ", "")

    # Check if it starts with +
    if not normalized.startswith("+"):
        raise ValueError("Phone number must start with country code (e.g., +595)")

    # For Paraguayan numbers, validate format
    if normalized.startswith("+595"):
        # Should be +595 followed by exactly 9 digits
        if len(normalized) != 13:
            raise ValueError(
                "Paraguayan phone number must be +595 followed by 9 digits"
            )

        # Check that everything after +595 is digits
        digits_part = normalized[4:]  # Skip +595
        if not digits_part.isdigit():
            raise ValueError("Phone number must contain only digits after country code")
    else:
        # For other countries, just ensure it has digits after the +
        if not normalized[1:].isdigit():
            raise ValueError("Phone number must contain only digits after country code")

    return normalized


def get_or_create_user(db: Session, phone_number: str):
    """
    Get existing user by phone number or create a new one.
    """
    from app.models.database import User

    user = db.query(User).filter(User.phone_number == phone_number).first()

    if user:
        return user

    user = User(phone_number=phone_number)
    db.add(user)
    db.commit()
    db.refresh(user)

    logging.info(f"CREATED USER: {user.id} - {user.phone_number}")
    return user


def get_or_create_conversation(openai_client: OpenAI, user: User, db: Session) -> str:
    """
    Get existing OpenAI conversation ID or create a new one for the user.
    """
    if user.openai_conversation_id:
        return user.openai_conversation_id

    conversation = openai_client.conversations.create()

    user.openai_conversation_id = conversation.id
    db.commit()
    db.refresh(user)

    logging.info(
        f"CREATED CONVERSATION: {user.id} - {user.phone_number}: {conversation.id}"
    )
    return conversation.id


def save_message(
    db: Session,
    recipient: str,
    sender: str,
    message_text: str,
    direction: MessageDirection,
    user_id: int = None,
):
    """Save a message to the database."""
    db_message = Message(
        recipient=recipient,
        sender=sender,
        message_text=message_text,
        direction=direction,
        user_id=user_id,
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message
