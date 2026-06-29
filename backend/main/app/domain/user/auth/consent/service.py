from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

import csv
import io
from typing import List, Optional

from kink import di, inject

from main.app.domain.user.auth.consent.content import LEGAL_DOCUMENT_CONTENT
from main.app.domain.user.auth.consent.models import (
    ConsentDocument,
    ConsentDocumentType,
    ConsentSignoffStatus,
    CreateConsentDocumentDto,
    CreateUserConsentDto,
    LegalDocumentDto,
    LegalDocumentSummaryDto,
    UpdateConsentDocumentDto,
    UserConsentHistoryItemDto,
    UserConsentHistoryPageDto,
)
from main.app.domain.user.auth.consent.repo import ConsentDocumentRepo, UserConsentRepo
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di["logger"]


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

    # ── Legal-document content (public marketing /legal/* pages) ─────────────

    async def seed_documents(self) -> None:
        """Idempotently upsert every legal document from the code content registry.

        Keyed on (type, consent_version): refreshes title/href/effective_at/body/
        signoff_status on an existing row, or inserts a new one. Safe to run on
        every boot (called from the runtime DataSeeder)."""
        for content in LEGAL_DOCUMENT_CONTENT.values():
            existing = await self._doc_repo.get_by_type_version(
                content.type, content.consent_version
            )
            if existing:
                await self._doc_repo.update(existing.id, UpdateConsentDocumentDto(
                    title=content.title,
                    href=content.href,
                    body=content.body,
                    signoff_status=content.signoff_status,
                ))
            else:
                await self._doc_repo.create(CreateConsentDocumentDto(
                    type=content.type,
                    consent_version=content.consent_version,
                    effective_at=content.effective_at,
                    title=content.title,
                    href=content.href,
                    body=content.body,
                    signoff_status=content.signoff_status,
                ))

    async def get_legal_document(self, slug: str) -> Optional[LegalDocumentDto]:
        """Published legal document (incl. body) for a `/legal/{slug}` page.

        Backend owns the slug→document mapping (resolved via the stored href) so
        the frontend never derives it."""
        doc = await self._doc_repo.get_active_by_href(f"/legal/{slug}")
        if not doc:
            return None
        return LegalDocumentDto(
            type=ConsentDocumentType(doc.type),
            consent_version=doc.consent_version,
            effective_at=doc.effective_at,
            title=doc.title,
            href=doc.href,
            signoff_status=ConsentSignoffStatus(doc.signoff_status),
            body=doc.body,
        )

    async def list_legal_documents(self) -> List[LegalDocumentSummaryDto]:
        """Metadata for every published legal document (for sitemap / listings)."""
        docs = await self._doc_repo.list_active()
        return [
            LegalDocumentSummaryDto(
                type=ConsentDocumentType(d.type),
                consent_version=d.consent_version,
                effective_at=d.effective_at,
                title=d.title,
                href=d.href,
                signoff_status=ConsentSignoffStatus(d.signoff_status),
            )
            for d in docs
        ]

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

    # ── S57 — R19.4 consent history ──────────────────────────────────────────

    async def list_for_user(
        self, user_id: str, page: int = 0, page_size: int = 20
    ) -> UserConsentHistoryPageDto:
        rows, total = await self._user_consent_repo.list_for_user(
            user_id=user_id, offset=page * page_size, limit=page_size
        )
        items = [
            UserConsentHistoryItemDto(
                document_type=r.document_type,
                consent_version=r.consent_version,
                accepted_at=r.accepted_at,
                ip_address=r.ip_address,
                device_fingerprint=r.device_fingerprint,
            )
            for r in rows
        ]
        return UserConsentHistoryPageDto(items=items, total=total, page=page, page_size=page_size)

    async def export_for_user_csv(self, user_id: str) -> bytes:
        rows, _ = await self._user_consent_repo.list_for_user(
            user_id=user_id, offset=0, limit=10_000
        )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["document_type", "consent_version", "accepted_at", "ip_address", "device_fingerprint"])
        for r in rows:
            writer.writerow([
                r.document_type,
                r.consent_version,
                r.accepted_at.isoformat() if r.accepted_at else "",
                r.ip_address or "",
                r.device_fingerprint or "",
            ])
        return buf.getvalue().encode("utf-8")
