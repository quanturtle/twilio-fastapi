from openai import OpenAI
from twilio.rest import Client


def get_chatgpt_reply(openai_client: OpenAI, message: str, conversation_id: str) -> str:
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


def send_whatsapp_message(twilio_client: Client, whatsapp_number: str, recipient: str, message: str):
    """Send a WhatsApp message via Twilio."""
    twilio_client.messages.create(
        to=f'whatsapp:{recipient}',
        from_=f'whatsapp:{whatsapp_number}',
        body=message,
    )

