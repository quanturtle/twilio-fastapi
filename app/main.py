import os
import logging
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Form
from twilio.rest import Client
from openai import OpenAI
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.models.schemas import MessageHistory, User as UserSchema, UserUpdate
from app.models.database import Message, MessageDirection, User
from app.database import get_db, init_db, get_db_context

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('twilio').setLevel(logging.WARNING)

app = FastAPI(title="Twilio FastAPI ChatGPT WhatsApp Bot")

twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")


@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup."""
    init_db()


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
            raise ValueError("Paraguayan phone number must be +595 followed by 9 digits")
        
        # Check that everything after +595 is digits
        digits_part = normalized[4:]  # Skip +595
        if not digits_part.isdigit():
            raise ValueError("Phone number must contain only digits after country code")
    else:
        # For other countries, just ensure it has digits after the +
        if not normalized[1:].isdigit():
            raise ValueError("Phone number must contain only digits after country code")
    
    return normalized


def get_or_create_user(db: Session, phone_number: str) -> User:
    """
    Get existing user by phone number or create a new one.
    """
    user = db.query(User).filter(User.phone_number == phone_number).first()
    
    if user:
        return user
    
    user = User(phone_number=phone_number)
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logging.info(f"CREATED USER: {user.id} - {user.phone_number}")
    return user


def get_or_create_conversation(user: User, db: Session) -> str:
    """
    Get existing OpenAI conversation ID or create a new one for the user.
    """
    if user.openai_conversation_id:
        return user.openai_conversation_id
    
    conversation = openai_client.conversations.create()
    
    user.openai_conversation_id = conversation.id
    db.commit()
    db.refresh(user)
    
    logging.info(f"CREATED CONVERSATION: {user.id} - {user.phone_number}: {conversation.id}")
    return conversation.id


def get_chatgpt_reply(message: str, conversation_id: str) -> str:
    """Get a reply from ChatGPT for the given message using conversation state."""
    response = openai_client.responses.create(
        model="gpt-4.1",
        input=message,
        conversation=conversation_id,
        instructions="You are a helpful assistant that can answer questions directly to the point and concisely.",
        temperature=0.1,
        max_output_tokens=150,
    )
    return response.output[0].content[0].text


def send_whatsapp_message(recipient: str, message: str):
    """Send a WhatsApp message via Twilio."""
    twilio_client.messages.create(
        to=f'whatsapp:{recipient}',
        from_=f'whatsapp:{whatsapp_number}',
        body=message,
    )


def save_message(
    db: Session,
    recipient: str,
    sender: str,
    message_text: str,
    direction: MessageDirection,
    user_id: int = None
) -> Message:
    """Save a message to the database."""
    db_message = Message(
        recipient=recipient,
        sender=sender,
        message_text=message_text,
        direction=direction,
        user_id=user_id
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


def process_and_respond(recipient: str, message: str, whatsapp_number: str, conversation_id: str, user_id: int):
    """Background task to process message with ChatGPT and send response."""
    try:
        # Get ChatGPT response with conversation context
        reply_message = get_chatgpt_reply(message, conversation_id)
        
        # Send response via WhatsApp
        send_whatsapp_message(recipient, reply_message)
        
        logging.info(f"OUTGOING - recipient={recipient}, sender={whatsapp_number}, message={reply_message}")
        
        with get_db_context() as db:
            save_message(
                db=db,
                recipient=recipient,
                sender=whatsapp_number,
                message_text=reply_message,
                direction=MessageDirection.outgoing,
                user_id=user_id
            )
            
    except Exception as e:
        logging.error(f"ERROR PROCESSING MESSAGE: {str(e)}")


@app.post("/chat")
async def chat(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(...),
    To: str | None = Form(None),
    MessageSid: str | None = Form(None),
    db: Session = Depends(get_db)
):
    """
    Twilio webhook endpoint that receives WhatsApp messages,
    processes them with ChatGPT, and sends responses back.
    Returns immediately while processing happens in the background.
    Automatically creates users and conversations on first message.
    """
    try:
        # Validate and normalize phone numbers
        sender_number = validate_phone_number(From)
        recipient_number = validate_phone_number(To) if To else whatsapp_number
        
        # Get or create user for sender
        user = get_or_create_user(db, sender_number)
        
        # Get or create OpenAI conversation for this user
        conversation_id = get_or_create_conversation(user, db)
        
        # Save incoming message to database with user association
        save_message(
            db=db,
            recipient=recipient_number,
            sender=sender_number,
            message_text=Body,
            direction=MessageDirection.incoming,
            user_id=user.id
        )
        
        logging.info(f"INCOMING - recipient={recipient_number}, sender={sender_number}, user_id={user.id}, message={Body}")
        
        # Add background task to process and respond
        background_tasks.add_task(
            process_and_respond,
            recipient=sender_number,
            message=Body,
            whatsapp_number=whatsapp_number,
            conversation_id=conversation_id,
            user_id=user.id
        )
        
        return {"status": "received", "message": "Message received and being processed"}
        
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
    phone_number: str,
    user_update: UserUpdate,
    db: Session = Depends(get_db)
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
async def get_history(phone_number: str, limit: int = 50, db: Session = Depends(get_db)):
    """
    Retrieve conversation history for a specific user by phone number.
    """
    try:
        validated_phone = validate_phone_number(phone_number)
        user = db.query(User).filter(User.phone_number == validated_phone).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get messages for this user
        messages = db.query(Message).filter(
            Message.user_id == user.id
        ).order_by(Message.timestamp.desc()).limit(limit).all()
        
        if not messages:
            raise HTTPException(status_code=404, detail="No messages found for this user")
        
        return [
            MessageHistory(
                id=msg.id,
                recipient=msg.recipient,
                sender=msg.sender,
                message_text=msg.message_text,
                timestamp=msg.timestamp.isoformat(),
                direction=msg.direction.value,
                user_id=msg.user_id
            )
            for msg in messages
        ]
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Twilio FastAPI ChatGPT WhatsApp Bot"}

