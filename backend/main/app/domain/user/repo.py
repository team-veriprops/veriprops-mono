from typing import Optional, Type

from kink import inject
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from main.app.domain.user.auth.session.device.models import Device
from main.app.domain.user.models import (
    QueryUserDto,
    SearchUserDto,
    UpdateUserDto,
    User, _CreateUserDto,
)
from main.appodus_utils.db.repo import GenericRepo
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
                User.user_id == user_id
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
                User.user_id.in_(user_ids),
            )
        )

        rows = (await self._session.execute(stmt)).mappings().all()

        return [EmailRecipient(**row) for row in rows]
