from openai import OpenAI
from twilio.rest import Client

from app.config import Settings


def get_chatgpt_reply(
    openai_client: OpenAI, message: str, conversation_id: str, settings: Settings
) -> str:
    """Get a reply from ChatGPT for the given message using conversation state."""
    response = openai_client.responses.create(
        model=settings.model,
        input=message,
        conversation=conversation_id,
        instructions=settings.instructions,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
    )
    return response.output[0].content[0].text


def send_whatsapp_message(
    twilio_client: Client, whatsapp_number: str, recipient: str, message: str
):
    """Send a WhatsApp message via Twilio."""
    twilio_client.messages.create(
        to=f"whatsapp:{recipient}",
        from_=f"whatsapp:{whatsapp_number}",
        body=message,
    )
