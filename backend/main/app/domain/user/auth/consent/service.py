from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from datetime import datetime, timezone
from typing import List, Optional

from kink import di, inject

from main.app.domain.user.auth.consent.models import (
    ConsentDocument,
    ConsentDocumentType,
    CreateConsentDocumentDto,
    CreateUserConsentDto,
)
from main.app.domain.user.auth.consent.repo import ConsentDocumentRepo, UserConsentRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di["logger"]

# Default registry — must mirror frontend `lib/auth/consent.ts`. Seeded if empty.
DEFAULT_DOCUMENTS: list[CreateConsentDocumentDto] = [
    CreateConsentDocumentDto(
        type=ConsentDocumentType.PLATFORM_TERMS, consent_version="1.0.0",
        effective_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        title="Platform Terms of Service", href="/legal/terms",
    ),
    CreateConsentDocumentDto(
        type=ConsentDocumentType.PRIVACY_POLICY, consent_version="1.0.0",
        effective_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        title="Privacy Policy", href="/legal/privacy",
    ),
    CreateConsentDocumentDto(
        type=ConsentDocumentType.AGENT_TERMS, consent_version="1.0.0",
        effective_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        title="Agent Terms", href="/legal/agent-terms",
    ),
    CreateConsentDocumentDto(
        type=ConsentDocumentType.VERIFICATION_TERMS, consent_version="1.0.0",
        effective_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        title="Verification Terms", href="/legal/verification-terms",
    ),
    CreateConsentDocumentDto(
        type=ConsentDocumentType.REPORT_DISCLAIMER, consent_version="1.0.0",
        effective_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        title="Report Disclaimer", href="/legal/report-disclaimer",
    ),
]


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class ConsentService:
    def __init__(self, doc_repo: ConsentDocumentRepo, user_consent_repo: UserConsentRepo):
        self._doc_repo = doc_repo
        self._user_consent_repo = user_consent_repo

    async def get_current_for_signup(self) -> List[ConsentDocument]:
        return await self._doc_repo.list_current_for_types([
            ConsentDocumentType.PLATFORM_TERMS,
            ConsentDocumentType.PRIVACY_POLICY,
        ])

    async def get_current(self, doc_type: ConsentDocumentType) -> Optional[ConsentDocument]:
        return await self._doc_repo.get_current(doc_type)

    async def record_user_consent(
            self,
            user_id: str,
            document_type: ConsentDocumentType,
            consent_version: str,
            ip_address: Optional[str] = None,
            device_fingerprint: Optional[str] = None,
    ) -> None:
        await self._user_consent_repo.create(CreateUserConsentDto(
            user_id=user_id,
            document_type=document_type,
            consent_version=consent_version,
            accepted_at=Utils.datetime_now(),
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
        ))

    async def list_missing_required_consents(self, user_id: str) -> List[ConsentDocument]:
        """Returns the current consent_versions of any required consents the user has
        not yet accepted (or has only accepted an older consent_version of)."""
        required = [
            ConsentDocumentType.PLATFORM_TERMS,
            ConsentDocumentType.PRIVACY_POLICY,
        ]
        missing: List[ConsentDocument] = []
        for doc_type in required:
            current = await self._doc_repo.get_current(doc_type)
            if not current:
                continue
            latest_user = await self._user_consent_repo.latest_for_user(user_id, doc_type)
            if not latest_user or latest_user.consent_version != current.consent_version:
                missing.append(current)
        return missing
