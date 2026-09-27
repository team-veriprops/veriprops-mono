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
    ) -> Dict[str, Any]:
        """The envelope's ``data``. ``action`` completes "Could not …" in the raised sentence.

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
        if response.is_error or not self._is_ok(body):
            logger.error(
                f"{self._provider} refused to {action}: HTTP {response.status_code}, "
                f"message={body.get('message')!r}"
            )
            raise IntegrationException(f"Could not {action}: the payment gateway declined the request.")
        return body.get("data") or {}
