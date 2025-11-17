import os
import logging
from fastapi import FastAPI, Depends, HTTPException, Form
from twilio.rest import Client
from openai import OpenAI
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.models.schemas import MessageHistory, User as UserSchema, UserUpdate
from app.models.database import Message, MessageDirection, User
from app.database import (
    get_db,
    init_db,
    validate_phone_number,
    get_or_create_user,
    get_or_create_conversation,
    save_message,
)
from app.message_batcher import MessageBatcher
from app.config import get_settings

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("twilio").setLevel(logging.WARNING)

app = FastAPI(title="Twilio FastAPI ChatGPT WhatsApp Bot")

twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")


@app.on_event("startup")
async def startup_event():
    """Initialize database tables and message batcher on startup."""
    init_db()

    # Get settings instance
    settings = get_settings()

    # Initialize message batcher
    app.state.message_batcher = MessageBatcher(
        openai_client=openai_client,
        twilio_client=twilio_client,
        whatsapp_number=whatsapp_number,
        settings=settings,
    )
    logging.debug("Message batcher initialized")


@app.post("/chat")
async def chat(
    From: str = Form(...),
    Body: str = Form(...),
    To: str | None = Form(None),
    MessageSid: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """
    Twilio webhook endpoint that receives WhatsApp messages.
    Messages are batched per user with a 10-second debounce timer.
    Multiple messages within 10 seconds are combined and sent to ChatGPT as one request.
    Automatically creates users and conversations on first message.
    """
    try:
        # Validate and normalize phone numbers
        sender_number = validate_phone_number(From)
        recipient_number = validate_phone_number(To) if To else whatsapp_number

        # Get or create user for sender
        user = get_or_create_user(db, sender_number)

        # Get or create OpenAI conversation for this user
        conversation_id = get_or_create_conversation(openai_client, user, db)

        # Save incoming message to database with user association
        save_message(
            db=db,
            recipient=recipient_number,
            sender=sender_number,
            message_text=Body,
            direction=MessageDirection.incoming,
            user_id=user.id,
        )

        logging.info(
            f"INCOMING - recipient={recipient_number}, sender={sender_number}, user_id={user.id}, message={Body}"
        )

        # Add message to the batcher (will wait 10 seconds with debounce)
        await app.state.message_batcher.add_message(
            user_id=user.id,
            message=Body,
            phone_number=sender_number,
            conversation_id=conversation_id,
        )

        return {
            "status": "received",
            "message": "Message received and queued for processing",
        }

    except ValueError as e:
        logging.error(f"Phone number validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/users/{phone_number}", response_model=UserSchema)
async def get_user(phone_number: str, db: Session = Depends(get_db)):
    """
    Retrieve user information by phone number.
    """
    try:
        validated_phone = validate_phone_number(phone_number)
        user = db.query(User).filter(User.phone_number == validated_phone).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/users/{phone_number}", response_model=UserSchema)
async def update_user(
    phone_number: str, user_update: UserUpdate, db: Session = Depends(get_db)
):
    """
    Update user information (first_name, last_name, address).
    """
    try:
        # Validate phone number format
        validated_phone = validate_phone_number(phone_number)

        # Find user
        user = db.query(User).filter(User.phone_number == validated_phone).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update fields if provided
        if user_update.first_name is not None:
            user.first_name = user_update.first_name
        if user_update.last_name is not None:
            user.last_name = user_update.last_name
        if user_update.address is not None:
            user.address = user_update.address

        db.commit()
        db.refresh(user)

        logging.info(f"Updated user {validated_phone}")
        return user

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/users", response_model=list[UserSchema])
async def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List all users.
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@app.get("/history/{phone_number}", response_model=list[MessageHistory])
async def get_history(
    phone_number: str, limit: int = 50, db: Session = Depends(get_db)
):
    """
    Retrieve conversation history for a specific user by phone number.
    """
    try:
        validated_phone = validate_phone_number(phone_number)
        user = db.query(User).filter(User.phone_number == validated_phone).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get messages for this user
        messages = (
            db.query(Message)
            .filter(Message.user_id == user.id)
            .order_by(Message.timestamp.desc())
            .limit(limit)
            .all()
        )

        if not messages:
            raise HTTPException(
                status_code=404, detail="No messages found for this user"
            )

        return [
            MessageHistory(
                id=msg.id,
                recipient=msg.recipient,
                sender=msg.sender,
                message_text=msg.message_text,
                timestamp=msg.timestamp.isoformat(),
                direction=msg.direction.value,
                user_id=msg.user_id,
            )
            for msg in messages
        ]

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Twilio FastAPI ChatGPT WhatsApp Bot"}
