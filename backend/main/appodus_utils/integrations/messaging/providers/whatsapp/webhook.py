"""Meta Cloud API webhook receiver (PRD §26.3.3).

The channel's public front door. There is no session and no cookie here — the
`X-Hub-Signature-256` HMAC over the **raw** request body is the authentication, so this
class is the access control for everything inbound. It fails closed: an unconfigured app
secret rejects every delivery rather than waving it through.

Two availability rules shape the rest of it, both from how Meta treats a non-2xx reply —
it retries, then throttles, then disables the subscription outright:

* once a delivery is authenticated it is **always acknowledged**, even if our own
  downstream handling fails. Losing a message is recoverable; losing the subscription
  takes the channel down.
* one bad message never blocks the others in the same batch.

That is only safe because every inbound message is deduplicated on its `wamid`
downstream, so a Meta redelivery is a no-op rather than a duplicate conversation turn.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Dict, Optional

from httpx import QueryParams
from kink import di, inject
from starlette.responses import RedirectResponse, Response

from main.app.config.settings import IntegratedPlatform, settings
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER
from main.appodus_utils.domain.webhook.callback.model import QueryCallbackDto
from main.appodus_utils.exception.exceptions import UnauthorizedException
from main.appodus_utils.integrations.interface import BaseWebhookHandler
from main.appodus_utils.integrations.messaging.providers.whatsapp.inbound import normalize_webhook

logger = di["logger"]

_SIGNATURE_HEADER = "x-hub-signature-256"
_SIGNATURE_PREFIX = "sha256="


def _is_configured(secret: Optional[str]) -> bool:
    """A blank or placeholder secret is 'not configured', never 'no check needed'."""
    return bool((secret or "").strip()) and (secret or "").strip() != SECRET_PLACEHOLDER


@inject
class WhatsAppWebhookHandler(BaseWebhookHandler):
    """Terminates Meta webhooks: verifies, normalizes, and hands off (§26.3.3)."""

    def __init__(self):
        super().__init__(settings.WHATSAPP_APP_SECRET_KEY)
        # Resolved lazily: the inbound service lives in the app domain layer, which
        # imports this package — binding it at construction would close an import cycle.
        self._inbound_service = None

    @property
    def platform(self) -> IntegratedPlatform:
        return IntegratedPlatform.WHATSAPP

    async def validate_signature(self, body: bytes, headers: Dict) -> bool:
        if not _is_configured(self.platform_secret):
            logger.error(
                "WhatsApp webhook rejected: WHATSAPP_APP_SECRET_KEY is not configured."
            )
            return False

        supplied = _header(headers, _SIGNATURE_HEADER)
        if not supplied.startswith(_SIGNATURE_PREFIX):
            return False
        supplied_digest = supplied[len(_SIGNATURE_PREFIX):]
        if not supplied_digest:
            return False

        expected = hmac.new(
            key=self.platform_secret.encode(), msg=body, digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(supplied_digest, expected)

    async def webhook_replay_handler(self, callback: QueryCallbackDto) -> None:
        # Redelivery is handled by wamid deduplication at ingest, not by replaying
        # stored callbacks.
        return None

    async def _process_verify_webhook_payload(self, payload: QueryParams) -> str:
        """Meta's subscription handshake: echo `hub.challenge` for the right token."""
        verify_token = settings.WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN
        if not _is_configured(verify_token):
            raise UnauthorizedException(
                "WhatsApp webhook verify token is not configured."
            )

        mode = payload.get("hub.mode")
        supplied = payload.get("hub.verify_token") or ""
        if mode != "subscribe" or not hmac.compare_digest(str(supplied), str(verify_token)):
            raise UnauthorizedException("Invalid WhatsApp webhook verification request.")

        return str(payload.get("hub.challenge") or "")

    async def _process_handle_redirect_payload(
        self, payload: QueryParams, headers: Dict, response: Response
    ) -> Optional[RedirectResponse]:
        # WhatsApp has no redirect leg — inbound arrives by webhook only.
        return None

    async def handle_webhook(self, body: bytes, headers: Dict) -> None:
        """Authenticate, then acknowledge unconditionally.

        Overrides the base flow deliberately: the base wraps processing in a retry that
        re-raises, which would surface a downstream failure to Meta as a non-2xx.
        """
        self._log_event(body, headers)
        if not await self.validate_signature(body, headers):
            raise UnauthorizedException("Invalid signature")

        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            # Signed but unparseable — nothing to do, and nothing Meta can fix by retrying.
            logger.warning("WhatsApp webhook body was signed but not valid JSON; ignoring.")
            return None

        await self._process_handle_webhook_payload(payload)
        return None

    async def _process_handle_webhook_payload(self, payload_dict: Dict) -> Dict:
        """Normalize a verified delivery and ingest each customer message.

        Per-message error isolation: one message that cannot be ingested must not stop
        the others in the same batch, and must not turn into a non-2xx for Meta.
        """
        messages = normalize_webhook(payload_dict)
        if not messages:
            # Delivery receipts and account notices land here — acknowledged, no work.
            return {"ingested": 0}

        service = self._resolve_inbound_service()
        ingested = 0
        for message in messages:
            try:
                await service.ingest(message)
                ingested += 1
            except Exception:
                # Log the id, never the content: inbound bodies are customer PII.
                logger.exception(
                    "Failed to ingest inbound WhatsApp message {}", message.wamid
                )
        return {"ingested": ingested}

    def _resolve_inbound_service(self):
        if self._inbound_service is None:
            from main.app.domain.channel.whatsapp.inbound.service import WhatsAppInboundService

            self._inbound_service = di[WhatsAppInboundService]
        return self._inbound_service


def _header(headers: Dict, name: str) -> str:
    """Header lookup that tolerates the casing of whatever server parsed the request."""
    if name in headers:
        return str(headers[name] or "")
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return str(value or "")
    return ""
