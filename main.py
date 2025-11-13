import os
import json
from fastapi import FastAPI, Form, Response
from twilio.rest import Client
from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Initialize clients
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")


# Pydantic models
class ChatInput(BaseModel):
    recipient: str
    message: str


class ChatResponse(BaseModel):
    recipient: str
    sender: str
    message: str


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


@app.post("/chat", response_model=ChatResponse)
async def chat(input: ChatInput):
    """
    Twilio webhook endpoint that receives WhatsApp messages,
    processes them with ChatGPT, and sends responses back.
    """
    # Get ChatGPT response
    reply_message = get_chatgpt_reply(input.message)
    
    # Send response via WhatsApp
    send_whatsapp_message(input.recipient, reply_message)
    
    return ChatResponse(
        recipient=input.recipient,
        sender=whatsapp_number,
        message=reply_message
    )


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Twilio FastAPI ChatGPT WhatsApp Bot"}

