import os
import logging
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Form
from twilio.rest import Client
from openai import OpenAI
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.models.schemas import MessageHistory
from app.models.database import Message, MessageDirection
from app.database import get_db, init_db
from app.database import SessionLocal

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


def get_chatgpt_reply(message: str) -> str:
    """Get a reply from ChatGPT for the given message."""
    response = openai_client.responses.create(
        model="gpt-4.1",
        input=message,
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


def process_and_respond(recipient: str, message: str, whatsapp_number: str):
    """
    Background task to process message with ChatGPT and send response.
    This runs asynchronously after the webhook returns.
    """
    try:
        # Get ChatGPT response
        reply_message = get_chatgpt_reply(message)
        
        # Send response via WhatsApp
        send_whatsapp_message(recipient, reply_message)
        
        logging.info(f"OUTGOING - recipient={recipient}, sender={whatsapp_number}, message={reply_message}")
        
        # Save outgoing message to database
        # Create a new database session for the background task
        db = SessionLocal()
        try:
            save_message(
                db=db,
                recipient=recipient,
                sender=whatsapp_number,
                message_text=reply_message,
                direction=MessageDirection.outgoing
            )

        finally:
            db.close()
            
    except Exception as e:
        # Log the error but don't crash the background task
        print(f"Error processing message: {str(e)}")


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
    """
    # Strip "whatsapp:" prefix from phone numbers
    sender_number = From.replace("whatsapp:", "")
    recipient_number = To.replace("whatsapp:", "") if To else whatsapp_number
    
    # Save incoming message to database
    save_message(
        db=db,
        recipient=recipient_number,
        sender=sender_number,
        message_text=Body,
        direction=MessageDirection.incoming
    )
    
    logging.info(f"INCOMING - recipient={recipient_number}, sender={sender_number}, message={Body}")
    
    # Add background task to process and respond
    background_tasks.add_task(
        process_and_respond,
        recipient=sender_number,
        message=Body,
        whatsapp_number=whatsapp_number
    )
    
    return {"status": "received", "message": "Message received and being processed"}


@app.get("/history/{recipient}", response_model=list[MessageHistory])
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

