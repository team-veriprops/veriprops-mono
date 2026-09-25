from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

from typing import Optional

from main.app.domain.user.auth.session.models import UserPersona
from main.appodus_utils.integrations.messaging.models import UserContactDto, EmailRecipient

from kink import di, inject

from main.app.domain.user.models import (
    OAUTH_PLACEHOLDER_PHONE,
    CreateUserDto,
    TrustStatus,
    UpdateUserDto,
    User, _CreateUserDto,
)
from main.app.domain.user.repo import UserRepo
from main.app.domain.user.validator import UserValidator
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.decorators.transactional import transactional
from main.appodus_utils.exception.exceptions import UserAlreadyExistsException

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
        """Create the account; `UserAlreadyExistsException` if the email is taken.

        The existence check answers the common case with a clear message. The insert itself
        is keyed on the unique normalised email, so a concurrent signup for the same address
        gets the same answer rather than failing on the constraint.
        """
        await self._user_validator.should_not_exist_by_email(dto.email)

        payload = _CreateUserDto(
            **dto.model_dump(),
            email_normalized=dto.email.strip().lower(),
            # An OAuth signup's placeholder is not a number anyone owns: stored as NULL, so it
            # neither collides with other OAuth accounts nor reads as a shared phone.
            phone_e164=(
                None if dto.phone == OAUTH_PLACEHOLDER_PHONE
                else _phone_e164(dto.phone_dial_code, dto.phone)
            ),
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
        user, created = await self._user_repo.insert_or_get(
            payload.model_dump(by_alias=False), ["email_normalized"],
        )
        if not created:
            raise UserAlreadyExistsException(email=dto.email)
        return user

    async def update_user(self, user_id: str, dto: UpdateUserDto) -> User:
        await self._user_validator.should_exist_by_id(user_id)
        await self._user_repo.update(user_id, dto)
        return await self._user_repo.get_model(user_id)

    async def add_persona(self, user_id: str, persona: UserPersona) -> User:
        """Grant *persona*, keeping every other one — including one granted concurrently."""
        await self._user_validator.should_exist_by_id(user_id)
        await self._user_repo.add_persona(user_id, persona)
        return await self._user_repo.get_model(user_id)

    async def add_credit_balance(self, user_id: str, amount_minor: int) -> None:
        """Credit spendable referral balance (§17.1)."""
        await self._user_repo.add_credit_balance(user_id, amount_minor)

    async def spend_credit_balance(self, user_id: str, amount_minor: int) -> None:
        """Debit referral balance spent on a price, never below zero (§17.1)."""
        await self._user_repo.spend_credit_balance(user_id, amount_minor)

    async def mark_email_verified(self, user_id: str) -> None:
        await self._user_repo.update(user_id, UpdateUserDto(email_verified=True))

    async def set_password_hash(self, user_id: str, password_hash: str) -> None:
        await self._user_repo.update(user_id, UpdateUserDto(password_hash=password_hash))

    async def reset_failed_login(self, user: User) -> None:
        """A successful sign-in clears the failure counter and any lock."""
        await self._user_repo.reset_failed_login(str(user.id))

    async def upgrade_trust_status_if_eligible(self, user_id: str, persona: UserPersona) -> None:
        # PRD §2.3: Customer trust = first successful payment;
        # Agent trust = first task submission. We expose this hook so
        # callers can elevate without re-implementing the rule.
        await self._user_repo.update(user_id, UpdateUserDto(trust_status=TrustStatus.TRUSTED.value))

    async def set_trust_status(self, user_id: str, trust_status: TrustStatus) -> None:
        # Admin override (§4.2) — unlike upgrade_trust_status_if_eligible this can
        # also downgrade. Auditing is the caller's responsibility (AdminUsersService).
        await self._user_repo.update(user_id, UpdateUserDto(trust_status=trust_status.value))


    async def get_user_contact(self, user_id: str) -> UserContactDto:
        return await self._user_repo.get_user_contact(user_id=user_id)

    async def get_email_recipients(self,user_ids: list[str]) -> list[EmailRecipient]:
        return await self._user_repo.get_email_recipients(user_ids=user_ids)
