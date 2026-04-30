from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import json
import uuid
from typing import Optional, Dict, List, Union

from httpx import AsyncClient, Timeout, Limits
from kink import di, inject
from requests.exceptions import HTTPError, RequestException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from main.app.config.settings import settings
from main.appodus_utils.integrations.document_sign.interface import IDocumentSignProvider
from main.appodus_utils.integrations.document_sign.models import Signer, SignActionType

logger: Logger = di['logger']

@inject
class ZohoDocumentSignProvider(IDocumentSignProvider):

    def __init__(self):
        self.client_id = settings.ZOHO_CLIENT_ID
        self.client_secret = settings.ZOHO_CLIENT_SECRET
        self.refresh_token = settings.ZOHO_REFRESH_TOKEN
        self.data_center = settings.ZOHO_DOC_SIGN_DATA_CENTER

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise ValueError("Missing Zoho credentials in environment variables.")

        self.client = AsyncClient(
            timeout=Timeout(30.0),  # 30-second timeout
            limits=Limits(max_connections=100)  # Connection pool
        )
        self.access_token = None
        self.last_token_refresh = None

    @property
    async def platform(self) -> str:
        return settings.ZOHO_PLATFORM_NAME

    # --------------------------
    # Document Signing Methods
    # --------------------------
    async def create_sign_request(
            self,
            request_name: str = "Document for Signature",
            signers: List[Signer] = None,
            file_path: Optional[str] = None,
            file_url: Optional[str] = None,
            idempotency_key: Optional[str] = None
    ) -> Dict:
        """Create signing request with idempotency support"""
        endpoint = "/requests"
        headers = {
            "X-Idempotency-Key": idempotency_key or str(uuid.uuid4())
        }
        data = {
            "requests": {
                "request_name": request_name,
                "signers": json.dumps(signers)
            }
        }

        if file_path:
            data = {
                "data": json.dumps(data)
            }
            with open(file_path, "rb") as file:
                files = {"file": (file_path, file, "application/pdf")}
                return await self._make_request(
                    "POST",
                    endpoint,
                    files=files,
                    data=data,
                    headers=headers
                )
        elif file_url:
            data["requests"]["file_url"] = file_url
            return await self._make_request(
                "POST",
                endpoint,
                json=data,
                headers=headers
            )
        else:
            raise ValueError("Either file_path or file_url must be provided.")

    async def get_request_status(self, request_id: str) -> Dict:
        """Get the status of a signature request."""
        endpoint = f"/requests/{request_id}"
        return await self._make_request("GET", endpoint)

    # --------------------------
    # Template Methods (Additional Examples)
    # --------------------------
    async def list_templates(self) -> List[Dict]:
        """List all available templates."""
        endpoint = "/templates"
        return await self._make_request("GET", endpoint)

    async def send_reminder(self, request_id: str, signer_email: str) -> Dict:
        """Send a reminder to a signer."""
        endpoint = f"/requests/{request_id}/remind"
        data = {"recipient_mail": signer_email}
        return await self._make_request("POST", endpoint, data=data)

    async def list_requests(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Paginated request listing"""
        return await self._make_request(
            "GET", f"/requests?limit={limit}&offset={offset}"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HTTPError, RequestException)),
        before_sleep=lambda _: logger.warning("Retrying due to failure...")
    )
    async def _refresh_access_token(self) -> str:
        """Force refresh access token"""
        logger.info("Refreshing access token...")

        token_url = f"{settings.ZOHO_DATA_CENTER}/oauth/v2/token"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            response = await self.client.post(token_url, params=params)
            response.raise_for_status()
            self.access_token = response.json()["access_token"]
            logger.info("Successfully refreshed access token")
            return self.access_token
        except Exception as e:
            logger.error(f"Failed to refresh access token: {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HTTPError, RequestException)),
        before_sleep=lambda _: logger.warning("Retrying API call...")
    )
    async def _make_request(
            self,
            method: str,
            endpoint: str,
            **kwargs
    ) -> Union[Dict, List]:
        """Smart request handler with token refresh on 401"""
        if not self.access_token:
            await self._refresh_access_token()

        url = f"{self.data_center}/api/v1{endpoint}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json",
            **kwargs.pop('headers', {})
        }

        try:
            response = await self.client.request(
                method, url, headers=headers, **kwargs
            )

            # Handle token expiration
            if response.status_code == 401:
                logger.warning("Token expired, refreshing...")
                await self._refresh_access_token()
                headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
                response = await self.client.request(method, url, headers=headers, **kwargs)

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
