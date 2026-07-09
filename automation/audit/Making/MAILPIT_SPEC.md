# Mailpit SMTP Provider Specification

## Overview

In dev, local, and test environments, all outbound email is captured by Mailpit via SMTP. No external mail provider is contacted. Production and staging always use Mailjet/SendGrid.

## How It Works

The `MessageRouter._load_routing_rules()` adds an email routing rule:

```python
"email": {
    "rules": [
        {
            "condition": lambda msg: settings.ENVIRONMENT not in {
                Environment.PRODUCTION, Environment.STAGING
            },
            "providers": [MessageProviderName.SMTP],
            "fallback_order": [MessageProviderName.MAILJET, MessageProviderName.SENDGRID_EMAIL],
        }
    ],
    "default": [MessageProviderName.MAILJET, MessageProviderName.SENDGRID_EMAIL],
}
```

When the condition is true (non-prod, non-staging), `SmtpEmailProvider` is selected. It connects to `settings.SMTP_HOST:SMTP_PORT` using `smtplib.SMTP` in a thread-pool executor (non-blocking).

## SmtpEmailProvider Hard-Fail Guard

`SmtpEmailProvider.send_message()` raises `ValueError` if called in production or staging:

```python
if env in {Environment.PRODUCTION, Environment.STAGING}:
    raise ValueError("SmtpEmailProvider must not be used in production or staging.")
```

This is defence-in-depth — the routing condition already excludes prod/staging, but the guard prevents accidental registration or misconfiguration from causing real mail to be sent via SMTP.

## Configuration

All SMTP settings live in `AppodusBaseSettings`:

| Setting | Default | Description |
|---|---|---|
| `SMTP_HOST` | `localhost` | SMTP server hostname |
| `SMTP_PORT` | `1025` | SMTP server port (Mailpit default) |
| `SMTP_USERNAME` | `None` | Optional — Mailpit requires no auth |
| `SMTP_PASSWORD` | `None` | Optional — Mailpit requires no auth |
| `SMTP_USE_TLS` | `false` | Enable STARTTLS |

## Running Mailpit (Docker Compose)

```yaml
services:
  mailpit:
    image: axllent/mailpit:latest
    ports:
      - "1025:1025"   # SMTP
      - "8025:8025"   # Web UI
    environment:
      MP_MAX_MESSAGES: 500
```

Web UI at `http://localhost:8025`. All captured emails appear here.

## Checking Email in Automation

Mailpit exposes a REST API:

```python
import httpx

async def get_latest_email():
    r = await httpx.get("http://localhost:8025/api/v1/messages")
    messages = r.json()["messages"]
    return messages[0] if messages else None

async def delete_all_emails():
    await httpx.delete("http://localhost:8025/api/v1/messages")
```

## Implementation

- `SmtpEmailProvider` — [backend/main/appodus_utils/integrations/messaging/providers/email/smtp.py](../../../backend/main/appodus_utils/integrations/messaging/providers/email/smtp.py)
- Routing rule — [backend/main/appodus_utils/integrations/messaging/router.py](../../../backend/main/appodus_utils/integrations/messaging/router.py)
- Settings — [backend/main/appodus_utils/config/settings.py](../../../backend/main/appodus_utils/config/settings.py)
