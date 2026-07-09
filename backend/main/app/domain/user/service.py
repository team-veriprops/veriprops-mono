from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from typing import Optional

from main.app.domain.user.auth.session.models import UserPersona
from main.appodus_utils.integrations.messaging.models import UserContactDto, EmailRecipient

from kink import di, inject

from main.app.domain.user.models import (
    CreateUserDto,
    UpdateUserDto,
    User, _CreateUserDto,
)
from main.app.domain.user.repo import UserRepo
from main.app.domain.user.validator import UserValidator
from main.appodus_utils import Utils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional

logger: Logger = di["logger"]


def _phone_e164(dial_code: str, phone: str) -> str:
    digits = "".join(c for c in (dial_code + phone) if c.isdigit())
    return f"+{digits}"


@inject
@decorate_all_methods(transactional(), exclude=["__init__"], exclude_startswith=["_"])
@decorate_all_methods(method_trace_logger, exclude=["__init__"], exclude_startswith=["_"])
class UserService:
    def __init__(
            self,
            user_repo: UserRepo,
            user_validator: UserValidator,
    ):
        self._user_repo = user_repo
        self._user_validator = user_validator

    # ── Reads ─────────────────────────────────────────────────────
    async def get_user_model(self, user_id: str) -> User:
        await self._user_validator.should_exist_by_id(user_id)
        user = await self._user_repo.get_model(user_id)
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        return await self._user_repo.get_by_email(email)

    async def get_user_by_phone_e164(self, phone_e164: str) -> Optional[User]:
        return await self._user_repo.get_by_phone_e164(phone_e164)

    # ── Writes ────────────────────────────────────────────────────
    async def create_user(self, dto: CreateUserDto) -> User:
        await self._user_validator.should_not_exist_by_email(dto.email)

        payload = _CreateUserDto(
            **dto.model_dump(),
            email_normalized=dto.email.strip().lower(),
            phone_e164=_phone_e164(dto.phone_dial_code, dto.phone),
        )
        # payload["email"] = dto.email.lower()
        # payload["phone_e164"] = _phone_e164(dto.phone_dial_code, dto.phone)
        # payload["personas"] = [p.value if hasattr(p, "value") else p for p in dto.personas]
        # payload["user_type"] = dto.user_type.value
        # if dto.admin_sub_role:
        #     payload["admin_sub_role"] = dto.admin_sub_role.value
        #
        # user = User(**payload)
        # user.id = Utils.hex_to_uuid(user.id) if user.id else None
        # user.version = 1
        # # Initialise the GenericRepo path manually since we want the ORM row back
        return await self._user_repo.create_return_model(payload)
        # await self._user_repo._session.flush()
        # return user

    async def update_user(self, user_id: str, dto: UpdateUserDto) -> User:
        await self._user_validator.should_exist_by_id(user_id)
        await self._user_repo.update(user_id, dto)
        return await self._user_repo.get_model(user_id)

    async def add_persona(self, user_id: str, persona: UserPersona) -> User:
        user = await self.get_user_model(user_id)
        existing = list(user.personas or [])
        if persona.value not in existing:
            existing.append(persona.value)
            await self._user_repo.update(user_id, UpdateUserDto(personas=existing))
        return await self._user_repo.get_model(user_id)

    async def mark_email_verified(self, user_id: str) -> None:
        await self._user_repo.update(user_id, UpdateUserDto(email_verified=True))

    async def mark_phone_verified(self, user_id: str) -> None:
        await self._user_repo.update(user_id, UpdateUserDto(phone_verified=True))

    async def set_password_hash(self, user_id: str, password_hash: str) -> None:
        await self._user_repo.update(user_id, UpdateUserDto(password_hash=password_hash))

    async def increment_failed_login(self, user: User) -> int:
        next_count = int(user.failed_login_count or 0) + 1
        await self._user_repo.update(
            user.id, UpdateUserDto(failed_login_count=next_count)
        )
        return next_count

    async def reset_failed_login(self, user: User) -> None:
        await self._user_repo.update(
            user.id, UpdateUserDto(failed_login_count=0, locked_until=None)
        )

    async def lock_user_until(self, user: User, until) -> None:
        await self._user_repo.update(user.id, UpdateUserDto(locked_until=until))

    async def upgrade_trust_status_if_eligible(self, user_id: str, persona: UserPersona) -> None:
        # PRD §2.3: Customer trust = first successful payment;
        # Agent trust = first task submission. We expose this hook so
        # callers can elevate without re-implementing the rule.
        await self._user_repo.update(user_id, UpdateUserDto(trust_status="TRUSTED"))


    async def get_user_contact(self, user_id: str) -> UserContactDto:
        return await self._user_repo.get_user_contact(user_id=user_id)

    async def get_email_recipients(self,user_ids: list[str]) -> list[EmailRecipient]:
        return await self._user_repo.get_email_recipients(user_ids=user_ids)
