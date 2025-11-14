# FastAPI Twilio ChatGPT WhatsApp Bot

A dockerized FastAPI application that receives WhatsApp messages via Twilio webhook, processes them with ChatGPT, sends responses back through the Twilio WhatsApp API, and stores conversation history in a PostgreSQL database.

## Project Structure

```
twilio-fastapi/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application
│   ├── database.py                # Database configuration
│   └── models/
│       ├── __init__.py
│       ├── schemas.py             # Pydantic models
│       └── database.py            # SQLAlchemy models
├── docker-compose.yml             # Docker services orchestration
├── Dockerfile                     # FastAPI app container
├── requirements.txt               # Python dependencies
├── env.example                    # Environment variables template
└── README.md
```

## Setup

### 1. Configure Environment Variables

Create a `.env` file in the project root using `env.example` as a template:

```bash
cp env.example .env
```

Edit `.env` with your credentials:

```
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid_here
TWILIO_AUTH_TOKEN=your_twilio_auth_token_here
TWILIO_WHATSAPP_NUMBER=your_twilio_whatsapp_number_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=twilio_db
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/twilio_db

# Ngrok Configuration
NGROK_AUTHTOKEN=your_ngrok_authtoken_here
```

### 2. Start All Services

Start all services (FastAPI app, PostgreSQL, ngrok) with Docker Compose:

```bash
docker-compose up -d
```

This will start:
- **fastapi-app**: The main application on port 8000
- **postgres**: PostgreSQL database on port 5432
- **ngrok**: Tunnel service with web interface on port 4040

### 3. Get Your Public URL

Access the ngrok web interface to get your public URL:

```bash
open http://localhost:4040
```

Or check the logs:

```bash
docker-compose logs ngrok
```

Your public ngrok URL will look like: `https://xxxx-xx-xx-xxx-xxx.ngrok-free.app`

### 4. Configure Twilio Webhook

1. Log in to your [Twilio Console](https://console.twilio.com/)
2. Navigate to your WhatsApp Sandbox settings or your approved WhatsApp number
3. Set the webhook URL for incoming messages to: `https://your-ngrok-url.ngrok-free.app/chat`
4. Make sure the HTTP method is set to `POST`

## Managing the Application

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f fastapi-app
docker-compose logs -f postgres
docker-compose logs -f ngrok
```

### Stop Services

```bash
docker-compose down
```

### Rebuild After Code Changes

```bash
docker-compose up -d --build
```

### Access Database

```bash
docker-compose exec postgres psql -U postgres -d twilio_db
```

## API Endpoints

### `POST /chat`
Twilio webhook endpoint that receives WhatsApp messages, processes them with ChatGPT, and sends responses back via WhatsApp. All messages are saved to the database.

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

### `GET /history/{recipient}`
Retrieve conversation history for a specific recipient phone number.

**Example Request:**
```bash
curl http://localhost:8000/history/+595975123456?limit=10
```

**Response:**
```json
[
    {
        "id": 2,
        "recipient": "+595975123456",
        "sender": "+14155238886",
        "message_text": "The eighth month of the year is August.",
        "timestamp": "2025-11-14T10:30:00",
        "direction": "outgoing"
    },
    {
        "id": 1,
        "recipient": "+14155238886",
        "sender": "+595975123456",
        "message_text": "What is the eighth month of the year?",
        "timestamp": "2025-11-14T10:29:55",
        "direction": "incoming"
    }
]
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