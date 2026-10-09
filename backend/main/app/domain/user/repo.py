from datetime import datetime
from typing import List, Optional, Type

from kink import inject
from sqlalchemy import String, cast, desc, literal, select, func, type_coerce, update as sa_update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.auth.session.device.models import Device
from main.app.domain.user.auth.session.models import UserPersona, UserType
from main.app.domain.user.models import (
    AccountStatus,
    AdminSubRole,
    QueryUserDto,
    SearchUserDto,
    UpdateUserDto,
    User, _CreateUserDto,
)
from main.appodus_utils import Utils
from main.appodus_utils.db.repo import GenericRepo
from main.appodus_utils.db.search import contains_text
from main.appodus_utils.db.types.phone import PhoneNumber
from main.appodus_utils.integrations.messaging.models import UserContactDto, PushToken, EmailRecipient


@inject
class UserRepo(GenericRepo[User, _CreateUserDto, UpdateUserDto, QueryUserDto, SearchUserDto]):
    def __init__(
        self,
        db: AsyncSession,
        model: Type[User] = User,
        query_dto: Type[QueryUserDto] = QueryUserDto,
    ):
        super().__init__(db, model, query_dto)
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(
            User.deleted.is_(False),
            User.email_normalized == email.strip().lower(),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _recipient_conditions(user_type: Optional[UserType], persona: Optional[UserPersona]) -> list:
        """Live users, narrowed to a user type and/or a persona (a JSONB containment) in SQL."""
        conditions = [User.deleted.is_(False)]
        if user_type is not None:
            conditions.append(User.user_type == user_type.value)
        if persona is not None:
            conditions.append(type_coerce(User.personas, JSONB).contains([persona.value]))
        return conditions

    async def list_recipient_ids_page(
        self,
        after: Optional[str],
        limit: int,
        *,
        user_type: Optional[UserType] = None,
        persona: Optional[UserPersona] = None,
    ) -> List[str]:
        """One keyset page of a broadcast audience (§18.1): the next *limit* user ids after
        *after*, in id order, as the 36-char str form notifications key on.

        Keyset rather than offset, so a page is the same set however often it is asked for, and
        a user who signs up mid-send lands on a later page instead of shifting every page after.
        """
        conditions = self._recipient_conditions(user_type, persona)
        if after is not None:
            conditions.append(User.id > self._ensure_uuid(after))
        stmt = select(User.id).where(*conditions).order_by(User.id).limit(limit)
        return [str(uid) for uid in (await self._session.execute(stmt)).scalars().all()]

    async def count_recipients(
        self, *, user_type: Optional[UserType] = None, persona: Optional[UserPersona] = None,
    ) -> int:
        """The size of the audience `list_recipient_ids_page` walks."""
        stmt = select(func.count(User.id)).where(*self._recipient_conditions(user_type, persona))
        return (await self._session.execute(stmt)).scalar_one()

    async def list_admins(
        self,
        sub_role_filter: Optional[AdminSubRole] = None,
        query: Optional[str] = None,
    ) -> List[User]:
        conditions = [User.deleted.is_(False), User.user_type == UserType.ADMIN.value]
        if sub_role_filter is not None:
            conditions.append(User.admin_sub_role == sub_role_filter.value)
        search = contains_text(query, User.first_name, User.last_name, User.email)
        if search is not None:
            conditions.append(search)
        stmt = select(User).where(*conditions)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def page_users(
        self,
        *,
        offset: int,
        limit: int,
        query: Optional[str] = None,
        persona: Optional[str] = None,
        user_type: Optional[str] = None,
        trust_status: Optional[str] = None,
        account_status: Optional[str] = None,
    ) -> tuple[List[User], int]:
        """Paged all-users directory for the admin panel (PRD §4.2), newest first.

        Filters are pre-validated enum values (the controller coerces through the
        enums), so the persona JSON-text match below never sees free-form input.
        """
        conditions = [User.deleted.is_(False)]
        if user_type:
            conditions.append(User.user_type == user_type)
        if trust_status:
            conditions.append(User.trust_status == trust_status)
        if account_status:
            conditions.append(User.account_status == account_status)
        if persona:
            # personas is a JSON list of enum values; a quoted-substring match is
            # dialect-portable (JSONB @> is Postgres-only) and safe on enum input.
            conditions.append(cast(User.personas, String).like(f'%"{persona}"%'))
        search = contains_text(query, User.first_name, User.last_name, User.email, User.phone_e164)
        if search is not None:
            conditions.append(search)
        base = select(User).where(*conditions)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(desc(User.date_created)).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total or 0

    async def suspend_user(self, user_id: str, *, reason: str, admin_id: str, at: datetime) -> None:
        stmt = (
            sa_update(User)
            .where(User.id == self._ensure_uuid(user_id), User.deleted.is_(False))
            .values(
                account_status=AccountStatus.SUSPENDED.value,
                suspended_at=at,
                suspension_reason=reason,
                suspended_by=admin_id,
            )
        )
        await self._session.execute(stmt)

    async def reactivate_user(self, user_id: str) -> None:
        stmt = (
            sa_update(User)
            .where(User.id == self._ensure_uuid(user_id), User.deleted.is_(False))
            .values(
                account_status=AccountStatus.ACTIVE.value,
                suspended_at=None,
                suspension_reason=None,
                suspended_by=None,
            )
        )
        await self._session.execute(stmt)

    async def increment_failed_login(self, user_id: str) -> int:
        """Count one failed password attempt and return the new total, in one statement.

        Computed in SQL so concurrent wrong passwords each count; a read-add-write would let
        a burst of attempts share one increment and never reach the lockout threshold.
        """
        stmt = (
            sa_update(User)
            .where(User.id == self._ensure_uuid(user_id))
            .values(failed_login_count=func.coalesce(User.failed_login_count, 0) + 1)
            .returning(User.failed_login_count)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def lock_until(self, user_id: str, until: datetime) -> None:
        stmt = sa_update(User).where(User.id == self._ensure_uuid(user_id)).values(locked_until=until)
        await self._session.execute(stmt)

    async def reset_failed_login(self, user_id: str) -> None:
        """Clear the counter **and** the lock. A statement, because the model-update path
        drops None values and so could never clear `locked_until`."""
        stmt = (
            sa_update(User)
            .where(User.id == self._ensure_uuid(user_id))
            .values(failed_login_count=0, locked_until=None)
        )
        await self._session.execute(stmt)

    async def add_persona(self, user_id: str, persona: UserPersona) -> Optional[User]:
        """Append *persona* in SQL, only when the user lacks it; the updated row, or None.

        A grant read-modify-written in Python lets two concurrent grants (AGENT from an
        application, CUSTOMER from the persona switch) each write back the list they read,
        and one persona is silently lost — an authorization bug. Appending in the statement
        works on the row as committed.
        """
        personas = type_coerce(User.personas, JSONB)
        await self._flush_pending()
        stmt = (
            sa_update(User)
            .where(User.id == self._ensure_uuid(user_id), ~personas.contains([persona.value]))
            .values(
                personas=personas.op("||")(literal([persona.value], JSONB)),
                version=User.version + 1,
                date_updated=Utils.datetime_now(),
            )
            .returning(User)
            .execution_options(populate_existing=True, synchronize_session=False)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_credit_balance(self, user_id: str, amount_minor: int) -> None:
        """Add to the spendable referral credit in SQL, so concurrent credits all land."""
        stmt = (
            sa_update(User)
            .where(User.id == self._ensure_uuid(user_id))
            .values(credit_balance_kobo=func.coalesce(User.credit_balance_kobo, 0) + amount_minor)
        )
        await self._session.execute(stmt)

    async def spend_credit_balance(self, user_id: str, amount_minor: int) -> None:
        """Take up to *amount_minor* off the credit balance in SQL, never below zero.

        Clamped because the credit may have been spent elsewhere since it was applied to a
        price; the statement reads the balance as committed, so two spends cannot both take
        the same credit.
        """
        balance = func.coalesce(User.credit_balance_kobo, 0)
        stmt = (
            sa_update(User)
            .where(User.id == self._ensure_uuid(user_id))
            .values(credit_balance_kobo=balance - func.least(amount_minor, balance))
        )
        await self._session.execute(stmt)

    async def demote_to_user(self, user_id: str) -> None:
        stmt = (
            sa_update(User)
            .where(User.id == user_id, User.deleted.is_(False))
            .values(user_type=UserType.USER.value, admin_sub_role=None)
        )
        await self._session.execute(stmt)

    async def get_by_phone_e164(self, phone_e164: str) -> Optional[User]:
        stmt = select(User).where(
            User.deleted.is_(False),
            User.phone_e164 == phone_e164,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_contact(
            self,
            user_id: str
    ) -> UserContactDto:
        # Profile
        profile_stmt = (
            select(
                User.email,
                User.first_name,
                User.last_name,
                User.phone_dial_code,
                User.phone
            )
            .where(
                User.deleted.is_(False),
                # users.id is the PK (uuid) — recipient user_ids travel as 36-char strings.
                User.id == self._ensure_uuid(user_id)
            )
            .limit(1)
        )

        profile = (await self._session.execute(profile_stmt)).first()

        # Devices
        device_stmt = (
            select(
                Device.device_id,
                Device.push_provider_type,
                Device.push_token
            )
            .where(
                Device.deleted.is_(False),
                Device.user_id == user_id
            )
        )

        devices = (await self._session.execute(device_stmt)).all()

        web_tokens = []
        ios_tokens = []
        android_tokens = []

        for device in devices:
            token = PushToken(
                token=device.push_token,
                device_id=device.device_id
            )

            provider = device.push_provider_type.lower()

            if provider == "webpush":
                web_tokens.append(token)

            elif provider == "apns":
                ios_tokens.append(token)

            elif provider == "fcm":
                android_tokens.append(token)

        email = profile.email if profile else ""
        phone_dial_code = profile.phone_dial_code if profile else ""
        phone_number = profile.phone if profile else ""
        firstname = profile.first_name if profile else ""
        lastname = profile.last_name if profile else ""

        fullname = " ".join(part for part in [str(firstname), str(lastname)] if part)

        return UserContactDto(
            email=email,
            full_name=fullname,
            first_name=str(firstname),
            last_name=str(lastname),
            phone=PhoneNumber(dial_code=str(phone_dial_code), number=str(phone_number)),
            web_push_token=web_tokens,
            ios_push_token=ios_tokens,
            android_push_token=android_tokens,
        )

    async def get_email_recipients(self, user_ids: list[str]) -> list[EmailRecipient]:

        if not user_ids:
            return []

        fullname = func.trim(
            func.coalesce(User.first_name, "")
            + " "
            + func.coalesce(User.last_name, "")
        ).label("fullname")

        stmt = (
            select(
                User.email,
                fullname,
            )
            .where(
                User.deleted.is_(False),
                User.id.in_([self._ensure_uuid(u) for u in user_ids]),
            )
        )

        rows = (await self._session.execute(stmt)).mappings().all()

        return [EmailRecipient(**row) for row in rows]

    async def erase_user(self, user_id: str, short_user_id: str):
        await self._session.execute(
            sa_update(User)
            .where(User.id == user_id)
            .values(
                email=f"deleted_{short_user_id}@erased.veriprops.ng",
                email_normalized=f"deleted_{short_user_id}@erased.veriprops.ng",
                phone="",
                phone_e164=None,
                first_name="Deleted",
                last_name="User",
                password_hash=None,
            )
        )

    async def has_active_verification(self, user_id: str, non_terminal_verification_status: frozenset[str]) -> bool:
        from main.app.domain.verification.models import Verification
        stmt = select(Verification).where(
            Verification.deleted.is_(False),
            Verification.customer_id == user_id,
            Verification.status.in_(list(non_terminal_verification_status)),
        ).limit(1)
        result = await self._session.execute(stmt)

        return result.scalar_one_or_none() is not None

