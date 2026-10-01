"""One HTTP path for every payment-gateway call.

Each provider wraps its answer in an envelope with a success flag (Flutterwave
``"status": "success"``, Paystack ``"status": true``) and may answer a failed request with
HTTP 200. This helper sends the bearer-authenticated request, checks both the HTTP status and
the envelope, and turns any failure into an ``IntegrationException`` carrying our sentence.
The provider's message, which can name keys, accounts and amounts, is logged and never
raised.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

import httpx
from kink import di

from main.appodus_utils.integrations.exception.exceptions import IntegrationException

if TYPE_CHECKING:
    from loguru import Logger

logger: Logger = di["logger"]


class GatewayNotFound(Exception):
    """The gateway has no record of the thing asked for (a reference nobody paid)."""


class GatewayDeclined(IntegrationException):
    """The gateway answered and refused the request (a 4xx, or a 2xx whose envelope says no).

    Only this proves nothing happened. An unreachable gateway or a 5xx raises the plain
    ``IntegrationException``: the request may have landed, so a money move must be looked up
    by its reference before it is called failed.

    ``provider_message`` keeps the gateway's own words ("balance is not enough") for staff
    screens such as a failed payout's reason. It is never part of the exception's message,
    which is what an error response would carry."""

    def __init__(self, message: str, provider_message: Optional[str] = None):
        super().__init__(message)
        self.provider_message = provider_message


class GatewayHttp:
    def __init__(self, provider: str, base_url: str, secret_key: str, is_ok: Callable[[Dict[str, Any]], bool]):
        self._provider = provider
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._is_ok = is_ok

    async def request(
        self,
        method: str,
        path: str,
        *,
        action: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        not_found_when: Optional[Callable[[int, Dict[str, Any]], bool]] = None,
        envelope: bool = False,
    ) -> Any:
        """The envelope's ``data`` (the whole envelope with ``envelope=True``, for a caller
        that pages through ``meta``). ``action`` completes "Could not …" in the raised sentence.

        ``not_found_when`` recognises the provider's "no such record" answer, which raises
        ``GatewayNotFound`` instead of a failure so the caller can treat it as an answer."""
        client: httpx.AsyncClient = di[httpx.AsyncClient]
        try:
            response = await client.request(
                method, f"{self._base_url}{path}", headers=self._headers, json=json, params=params,
            )
        except httpx.HTTPError as e:
            logger.error(f"{self._provider} unreachable while trying to {action}: {e!r}")
            raise IntegrationException(f"Could not {action}: the payment gateway is unreachable.") from e

        try:
            body: Dict[str, Any] = response.json()
        except ValueError:
            body = {}

        if not_found_when is not None and not_found_when(response.status_code, body):
            raise GatewayNotFound()
        if response.status_code >= 500:
            logger.error(f"{self._provider} failed while trying to {action}: HTTP {response.status_code}")
            raise IntegrationException(f"Could not {action}: the payment gateway is unavailable.")
        if response.is_error or not self._is_ok(body):
            logger.error(
                f"{self._provider} refused to {action}: HTTP {response.status_code}, "
                f"message={body.get('message')!r}"
            )
            provider_message = body.get("message")
            raise GatewayDeclined(
                f"Could not {action}: the payment gateway declined the request.",
                provider_message=str(provider_message)[:500] if provider_message else None,
            )
        if envelope:
            return body
        return body.get("data") or {}
