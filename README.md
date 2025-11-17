# FastAPI Twilio ChatGPT WhatsApp Bot

A dockerized FastAPI application that receives WhatsApp messages via Twilio, processes them with ChatGPT, and responds back through WhatsApp. All conversations are stored in PostgreSQL.

## Project Structure

```
twilio-fastapi/
├── app/
│   ├── main.py              # FastAPI application
│   ├── database.py          # Database configuration
│   ├── message_batcher.py   # Message batching logic
│   ├── utils.py             # Utility functions
│   └── models/
│       ├── schemas.py       # Pydantic models
│       └── database.py      # SQLAlchemy models
├── img/                     # Documentation images
├── docker-compose.yml       # Docker orchestration
├── Dockerfile
├── requirements.txt
└── README.md
```

## Prerequisites

### 1. Get Ngrok Auth Token

Sign up at [ngrok.com](https://ngrok.com/) and get your auth token from the dashboard.

![Ngrok Interface](img/ngrok.png)

### 2. Set Up Twilio WhatsApp

* Create a [Twilio account](https://www.twilio.com/try-twilio)
* Go to your [Twilio Console](https://console.twilio.com/)

![Twilio Console](img/twilio_console.png)

### 3. Set up WhatsApp Sandbox

![Twilio Sandbox Settings](img/twilio_sandbox_settings.png)

## Setup

### Configure Environment Variables

Your public URL will look like: `https://xxxx-xx-xx-xxx-xxx.ngrok-free.app`

Create a `.env` file in the project root with your credentials:

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

### Start All Services

```bash
docker compose up --build
```

This starts:
- **fastapi-app**: Application on port 8000
- **postgres**: Database on port 5432
- **ngrok**: Tunnel with web interface on port 4040

## Managing the Application

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f fastapi-app
docker compose logs -f postgres
docker compose logs -f ngrok
```

### Stop Services

```bash
docker compose down
```

### Rebuild After Code Changes

```bash
docker compose up -d --build
```

### Access Database

```bash
docker compose exec postgres psql -U postgres -d twilio_db
```

## API Endpoints

### `POST /chat`
Webhook endpoint for WhatsApp messages (receives Twilio form data). Processes with ChatGPT and responds via WhatsApp.

```bash
curl -X POST http://localhost:8000/chat \
  -d "From=whatsapp:+595975123456" \
  -d "Body=Hello!" \
  -d "To=whatsapp:+14155238999"
```

### `GET /history/{recipient}`
Get conversation history for a phone number.

```bash
curl http://localhost:8000/history/+595975123456?limit=10
```

### `GET /`
Health check endpoint.

```bash
curl http://localhost:8000/
```