"""The session → DTO mapper (PRD §7.6, D57).

Small, but it earned its own file. `WhatsAppBotSessionService` is wrapped by
`decorate_all_methods`, which decorates **every** method on the class — a `@staticmethod`
included — so a pure mapper defined inside it returns a coroutine instead of a DTO. That
failed nowhere except at runtime, as a 500 on an endpoint whose service call had already
succeeded, and a live drive-through was what found it.

Hence the shape being defended here: the mapper is a module-level function, and calling it
returns a DTO rather than something awaitable.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest

from main.app.domain.channel.whatsapp.bot.session.models import (
    BotFlow,
    BotMode,
    BotSessionDto,
    EscalationReason,
    WhatsAppBotSession,
)
from main.app.domain.channel.whatsapp.bot.session.service import to_bot_session_dto

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _row(**overrides) -> WhatsAppBotSession:
    session = WhatsAppBotSession()
    session.phone_e164 = "+2348012345678"
    session.mode = BotMode.BOT.value
    session.step = 0
    session.unmatched_count = 0
    session.current_flow = None
    session.last_escalation_reason = None
    session.mode_changed_at = None
    session.last_escalated_at = None
    session.last_inbound_at = NOW
    for field, value in overrides.items():
        setattr(session, field, value)
    return session


def test_the_mapper_returns_a_dto_not_a_coroutine():
    """The regression: a mapper living on the decorated service returned an un-awaited
    coroutine, and FastAPI answered 500 while every log line said the call had worked."""
    result = to_bot_session_dto(_row())

    assert isinstance(result, BotSessionDto)
    assert not inspect.iscoroutine(result)


def test_db_strings_come_back_as_enums():
    """The row stores strings; the wire contract is enums. A mismatch here is the kind of
    thing that only shows up as a validation error at response time."""
    dto = to_bot_session_dto(
        _row(
            mode=BotMode.HUMAN.value,
            current_flow=BotFlow.STATUS.value,
            last_escalation_reason=EscalationReason.GUARDRAIL_TOPIC.value,
            mode_changed_at=NOW,
            last_escalated_at=NOW,
        )
    )

    assert dto.mode == BotMode.HUMAN
    assert dto.current_flow == BotFlow.STATUS
    assert dto.last_escalation_reason == EscalationReason.GUARDRAIL_TOPIC
    assert dto.mode_changed_at == NOW


@pytest.mark.parametrize("field", ["current_flow", "last_escalation_reason"])
def test_an_empty_optional_stays_none_rather_than_becoming_an_enum(field):
    """A fresh session has neither, and coercing `None` through an enum raises."""
    dto = to_bot_session_dto(_row(**{field: None}))

    assert getattr(dto, field) is None


def test_the_dto_carries_no_case_data():
    """§7.3.4 — a bot session says where a *conversation* is, never what a case holds.
    Anything more would put customer data on an admin console field nobody asked for."""
    fields = set(BotSessionDto.model_fields)

    assert not fields & {"context", "step", "unmatched_count"}
