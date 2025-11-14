import os
from typing import List
from fastapi import FastAPI, Depends, HTTPException
from twilio.rest import Client
from openai import OpenAI
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.models.schemas import ChatInput, ChatResponse, MessageHistory
from app.models.database import Message, MessageDirection
from app.database import get_db, init_db

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Twilio FastAPI ChatGPT WhatsApp Bot")

# Initialize clients
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


def get_chatgpt_reply(message: str) -> str:
    """Get a reply from ChatGPT for the given message."""
    response = openai_client.responses.create(
        model="gpt-4.1",
        input=message
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
    direction: MessageDirection
) -> Message:
    """Save a message to the database."""
    db_message = Message(
        recipient=recipient,
        sender=sender,
        message_text=message_text,
        direction=direction
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


@app.post("/chat", response_model=ChatResponse)
async def chat(input: ChatInput, db: Session = Depends(get_db)):
    """
    Twilio webhook endpoint that receives WhatsApp messages,
    processes them with ChatGPT, and sends responses back.
    """
    # Save incoming message to database
    save_message(
        db=db,
        recipient=whatsapp_number,
        sender=input.recipient,
        message_text=input.message,
        direction=MessageDirection.incoming
    )
    
    # Get ChatGPT response
    reply_message = get_chatgpt_reply(input.message)
    
    # Send response via WhatsApp
    send_whatsapp_message(input.recipient, reply_message)
    
    # Save outgoing message to database
    save_message(
        db=db,
        recipient=input.recipient,
        sender=whatsapp_number,
        message_text=reply_message,
        direction=MessageDirection.outgoing
    )
    
    return ChatResponse(
        recipient=input.recipient,
        sender=whatsapp_number,
        message=reply_message
    )


@app.get("/history/{recipient}", response_model=List[MessageHistory])
async def get_history(recipient: str, limit: int = 50, db: Session = Depends(get_db)):
    """
    Retrieve conversation history for a specific recipient.
    
    Args:
        recipient: Phone number of the recipient
        limit: Maximum number of messages to retrieve (default: 50)
    """
    messages = db.query(Message).filter(
        (Message.recipient == recipient) | (Message.sender == recipient)
    ).order_by(Message.timestamp.desc()).limit(limit).all()
    
    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for this recipient")
    
    return [
        MessageHistory(
            id=msg.id,
            recipient=msg.recipient,
            sender=msg.sender,
            message_text=msg.message_text,
            timestamp=msg.timestamp.isoformat(),
            direction=msg.direction.value
        )
        for msg in messages
    ]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Twilio FastAPI ChatGPT WhatsApp Bot"}

