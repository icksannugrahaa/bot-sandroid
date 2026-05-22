# 🤖 OpenWA WhatsApp Bot

A simple Python bot that auto-replies to WhatsApp messages using the [OpenWA](https://github.com/rmyndharis/OpenWA) API Gateway.

## How It Works

```
WhatsApp User ──▶ OpenWA Server ──webhook──▶ This Bot (Flask)
                                                │
WhatsApp User ◀── OpenWA Server ◀──REST API──◀──┘
```

1. Someone sends you a WhatsApp message
2. OpenWA receives it and forwards it to your bot's webhook URL
3. Your bot processes the message and replies via the OpenWA REST API

## Setup

### 1. Install dependencies

```bash
cd bot-sandroid
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure your bot

Edit the values at the top of `bot.py` or use environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENWA_BASE_URL` | Your OpenWA server URL | `http://localhost:2785` |
| `OPENWA_API_KEY` | API key from OpenWA dashboard | `your-api-key` |
| `OPENWA_SESSION_ID` | Your registered session ID | `sess_abc123` |
| `BOT_PORT` | Port for the webhook listener | `5000` |

### 3. Run the bot

```bash
source venv/bin/activate
python bot.py
```

### 4. Register the webhook in OpenWA

```bash
curl -X POST http://localhost:2785/api/sessions/YOUR_SESSION_ID/webhooks \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "url": "http://YOUR_BOT_SERVER_IP:5000/webhook",
    "events": ["message.received"]
  }'
```

> **Note:** If your bot runs on the same server as OpenWA, use `http://localhost:5000/webhook`.
> If they're on different servers, use the bot server's public IP or domain.

## Bot Commands

| Command | Response |
|---------|----------|
| `hello` | `hello too 👋` |
| `ping` | `pong 🏓` |
| `help` | Shows available commands |

## Adding More Commands

Edit the `handle_message()` function in `bot.py`:

```python
def handle_message(data: dict) -> None:
    body = (data.get("body") or "").strip().lower()
    chat_id = data.get("chatId") or data.get("from", "")

    if body == "hello":
        send_text(chat_id, "hello too 👋")

    # Add your new command here:
    elif body == "goodbye":
        send_text(chat_id, "See you later! 👋")
```
