"""WhatsApp transport (PRD §7.3.3).

The webhook handler is imported here for the same reason every other integration package
imports its own: `WebhookHandlerFactory` builds its routing table from
`BaseWebhookHandler.__subclasses__()`, so a handler that is never imported is never
registered, and its endpoint answers "platform not supported".
"""
from main.appodus_utils.integrations.messaging.providers.whatsapp.webhook import (  # noqa: F401
    WhatsAppWebhookHandler,
)
