import hashlib
import hmac
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Callable, Optional

from fastapi import Request
from kink import di

logger: logging.Logger = di['logger']


class WebhookManager:
    def __init__(self):
        self.handlers = {}
        self.executor = ThreadPoolExecutor(max_workers=10)

    def register_handler(
            self,
            provider: str,
            event_type: str,
            callback: Callable
    ):
        if provider not in self.handlers:
            self.handlers[provider] = {}
        self.handlers[provider][event_type] = callback

    async def process_webhook(
            self,
            provider: str,
            request: Request,
            secret: Optional[str] = None
    ):
        # Verify signature if secret exists
        body = await request.body()
        if secret:
            signature = request.headers.get('X-Signature')
            if not self._verify_signature(body, secret, signature):
                raise ValueError("Invalid webhook signature")

        data = json.loads(body)
        event_type = self._get_event_type(provider, data)

        if provider in self.handlers and event_type in self.handlers[provider]:
            # Process in background thread
            self.executor.submit(
                self.handlers[provider][event_type],
                data
            )

    def _verify_signature(self, body: bytes, secret: str, signature: str) -> bool:
        digest = hmac.new(
            secret.encode(),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(digest, signature)

    def _get_event_type(self, provider: str, data: Dict) -> str:
        if provider == "twilio":
            return data.get("MessageStatus", "unknown")
        elif provider == "sendgrid":
            return data[0].get("event", "unknown")
        elif provider == "whatsapp":
            return data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("statuses", [{}])[0].get(
                "status", "unknown")
        return "unknown"


# Initialize webhook manager
webhook_manager = WebhookManager()
