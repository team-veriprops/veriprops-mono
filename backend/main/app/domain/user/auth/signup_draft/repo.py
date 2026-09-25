from datetime import datetime, timezone
from typing import Optional, Type

from kink import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.auth.signup_draft.models import (
    CreateSignupDraftDto,
    QuerySignupDraftDto,
    SearchSignupDraftDto,
    SignupDraft,
    UpdateSignupDraftDto,
)
from main.appodus_utils.db.repo import GenericRepo


@inject
class SignupDraftRepo(
    GenericRepo[
        SignupDraft,
        CreateSignupDraftDto,
        UpdateSignupDraftDto,
        QuerySignupDraftDto,
        SearchSignupDraftDto,
    ]
):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[SignupDraft] = SignupDraft,
        query_dto: Type[QuerySignupDraftDto] = QuerySignupDraftDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def upsert_active(
            self, *, email: str, step: int, payload: str, expires_at: datetime,
    ) -> SignupDraft:
        """Save the live draft for *email* in one statement, creating or overwriting it.

        Keyed on the partial unique index over live rows, so an expired draft is overwritten
        rather than blocking a new one, and two concurrent saves can't both insert.
        """
        return await self.upsert(
            {"email": email, "step": step, "payload": payload, "expires_at": expires_at},
            ["step", "payload", "expires_at"],
            unique_index="uq_signup_drafts_email",
        )

    async def get_active_by_email(self, email: str) -> Optional[SignupDraft]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(SignupDraft)
            .where(
                SignupDraft.deleted.is_(False),
                SignupDraft.email == email.lower(),
                SignupDraft.expires_at > now,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
