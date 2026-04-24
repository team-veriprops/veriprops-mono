"""
# --- Example Usage ---
async def demo():
    zoho = ZohoDocumentSignProvider()
    try:
        # Paginated listing with auto-retry
        requests = await zoho.list_requests(limit=5)
        logger.info(f"First 5 requests: {requests}")

        _signers = [
            Signer(
                email="signer1@example.com",
                name="John Doe",
                role="Signer 1",
                action_type=SignActionType.SIGN,
                signing_order=1
            )
        ]

        # Create with idempotency
        await zoho.create_sign_request(
            file_url="https://example.com/doc.pdf",
            signers=_signers,
            request_name="Sign Land Purchase Agreement",
            idempotency_key="contract_123"
        )
    except Exception as e:
        logger.error(f"Operation failed: {e}")
"""
from abc import abstractmethod, ABC
from typing import Optional, Dict, List


class IDocumentSignProvider(ABC):


    @property
    @abstractmethod
    def platform(self) -> str:
        pass

    @abstractmethod
    async def create_sign_request(
            self,
            request_name: str,
            signers: List[Dict],
            file_path: Optional[str] = None,
            file_url: Optional[str] = None,
            idempotency_key: Optional[str] = None
    ) -> Dict:
        pass

    @abstractmethod
    async def get_request_status(self, request_id: str) -> Dict:
        pass

    @abstractmethod
    async def list_templates(self) -> List[Dict]:
        pass

    @abstractmethod
    async def send_reminder(self, request_id: str, signer_email: str) -> Dict:
        pass
