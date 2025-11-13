# FastAPI Twilio ChatGPT WhatsApp Bot

A simple dockerized FastAPI application that receives WhatsApp messages via Twilio webhook, processes them with ChatGPT, and sends responses back through the Twilio WhatsApp API.

## Install
Create a `.env` file in the project root with the following variables:

```
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_WHATSAPP_NUMBER=your_twilio_whatsapp_number_here
OPENAI_API_KEY=your_openai_api_key_here
```

## Build the Docker Image

```bash
docker build -t twilio-fastapi .
```

## Run the Container

```bash
docker run -d -p 8000:8000 --env-file .env twilio-fastapi
```

## Configure Twilio Webhook

1. Log in to your Twilio Console
2. Navigate to your WhatsApp Sandbox settings or your approved WhatsApp number
3. Set the webhook URL for incoming messages to: `http://your-server-ip:8000/chat`
4. Make sure the HTTP method is set to `POST`

**For local development:**
- Use a tool like [ngrok](https://ngrok.com/) to expose your local server:
  ```bash
  ngrok http 8000
  ```
- Use the ngrok URL in your Twilio webhook configuration (e.g., `https://your-ngrok-url.ngrok.io/chat`)

## Endpoints

### `POST /chat`
Twilio webhook endpoint that receives WhatsApp messages, processes them with ChatGPT, and sends responses back via WhatsApp.

**Example Request:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": "+595975123456",
    "message": "What is the eighth month of the year?"
  }'
```

**Response:**
```json
{
    "recipient": "+595975123456",
    "sender": "+14155238886",
    "message": "The eighth month of the year is August."
}
```

### `GET /`
Health check endpoint to verify the service is running.

**Example Request:**
```bash
curl http://localhost:8000/
```

**Response:**
```json
{
    "status": "ok",
    "message": "Twilio FastAPI ChatGPT WhatsApp Bot"
}