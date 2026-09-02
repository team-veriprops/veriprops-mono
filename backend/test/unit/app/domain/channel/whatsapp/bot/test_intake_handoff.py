"""The chat→web seam (PRD §5.1, §7.5, D69/D71).

This is where four WhatsApp answers become a real draft. Everything upstream of it is a
conversation; everything downstream is the website's own, already-tested submission
wizard. So the properties worth pinning are the ones that would silently break the
handover:

* the answers come from the **token's** number, never the request;
* the draft is filled **by object**, because it may have been created moments earlier in
  the same uncommitted transaction;
* a second redemption finds nothing rather than re-seeding a draft the customer has since
  edited on the web.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.channel.whatsapp.bot.intake_handoff import (
    WhatsAppIntakeHandoffService,
)
from main.app.domain.channel.whatsapp.bot.session.models import WhatsAppBotSession
from main.appodus_utils import Utils
from main.appodus_utils.db.session import db_session_ctx
from main.appodus_utils.exception.exceptions import ResourceNotFoundException

PHONE = "+2348012345678"
CUSTOMER = "11111111-1111-1111-1111-111111111111"

COLLECTED = {
    "property": {
        "propertyType": "LAND",
        "address": "12 Ademola Street",
        "landmark": "",
        "state": "Lagos",
        "details": {},
    },
    "tier": "STANDARD",
    "currency": "NGN",
    "consentAccepted": False,
}


@pytest.fixture(autouse=True)
def mock_db_session():
    session = MagicMock()
    session.in_transaction.return_value = False

    @asynccontextmanager
    async def _begin():
        yield

    session.begin = _begin
    session.flush = AsyncMock()
    token = db_session_ctx.set(session)
    yield session
    db_session_ctx.reset(token)


def _bot_session(context) -> WhatsAppBotSession:
    row = WhatsAppBotSession()
    row.phone_e164 = PHONE
    row.context = context
    row.current_flow = "INTAKE"
    row.step = 4
    return row


def _service(bot_session):
    service = object.__new__(WhatsAppIntakeHandoffService)

    sessions = MagicMock()
    sessions.get = AsyncMock(return_value=bot_session)
    sessions.clear_flow = AsyncMock()
    service._whatsapp_bot_session_service = sessions

    draft = MagicMock()
    draft.id = Utils.generate_uuid()
    verifications = MagicMock()
    verifications.create_draft = AsyncMock(return_value=draft)
    # AsyncMock, matching the real method: `decorate_all_methods(transactional())`
    # makes every public method on the service a coroutine function.
    verifications.seed_draft_payload = AsyncMock(return_value=draft)
    service._verification_service = verifications

    return service, draft


async def test_the_collected_answers_become_a_seeded_draft():
    service, draft = _service(_bot_session({"intake": COLLECTED}))

    verification_id = await service.seed_draft(PHONE, CUSTOMER)

    assert verification_id == Utils.uuid_to_hex(draft.id)
    seeded = service._verification_service.seed_draft_payload.await_args.args
    assert seeded[0] is draft            # by object, not by id
    assert seeded[1] == 0                # the wizard opens on the property step
    assert seeded[2] == COLLECTED


async def test_the_draft_is_filled_by_object_not_re_fetched():
    """`create_draft` and the seeding happen in one transaction, where a re-fetch of a
    just-created row can come back empty — the seeding would then silently do nothing."""
    service, draft = _service(_bot_session({"intake": COLLECTED}))

    await service.seed_draft(PHONE, CUSTOMER)

    service._verification_service.seed_draft_payload.assert_awaited_once()
    assert service._verification_service.seed_draft_payload.await_args.args[0] is draft


async def test_the_answers_are_forgotten_once_they_are_a_draft():
    """Leaving them would let a second redemption re-seed a draft the customer has since
    edited on the web."""
    service, _draft = _service(_bot_session({"intake": COLLECTED}))

    await service.seed_draft(PHONE, CUSTOMER)

    service._whatsapp_bot_session_service.clear_flow.assert_awaited_once()


@pytest.mark.parametrize(
    "context", [None, {}, {"intake": None}, {"intake": {}}, {"vids": ["VP-1"]}],
    ids=["no-context", "empty", "null-intake", "empty-intake", "a-different-flow"],
)
async def test_a_conversation_with_no_answers_is_refused(context):
    """A link opened twice, or long after the conversation was reset. Seeding a blank
    draft would put a customer who answered four questions in front of an empty form."""
    service, _draft = _service(_bot_session(context))

    with pytest.raises(ResourceNotFoundException):
        await service.seed_draft(PHONE, CUSTOMER)

    service._verification_service.create_draft.assert_not_awaited()


async def test_a_number_that_never_wrote_to_us_is_refused():
    service, _draft = _service(None)

    with pytest.raises(ResourceNotFoundException):
        await service.seed_draft(PHONE, CUSTOMER)


async def test_the_answers_are_read_for_the_tokens_number():
    """The number comes from the signed token, so a signed-in stranger opening a forwarded
    link cannot seed their draft from someone else's conversation."""
    service, _draft = _service(_bot_session({"intake": COLLECTED}))

    await service.seed_draft(PHONE, CUSTOMER)

    service._whatsapp_bot_session_service.get.assert_any_await(PHONE)
