"""`/dev/scenario` — a customer who reaches their first payment with an unverified phone.

The browser spec for the pay-step phone gate (§10.5) needs that state on demand, and the
builder must refuse the combination it cannot honour: a stage that pays needs the gate cleared.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from main.app.core.state.status import VerificationStatus
from main.app.domain.dev.scenario import (
    BuildScenarioDto,
    DevScenarioService,
    ScenarioAccountDto,
    ScenarioStage,
)
from main.appodus_utils.exception.exceptions import ValidationException


def _service(people_kwargs: dict):
    svc = object.__new__(DevScenarioService)

    async def run_inline(action):
        return await action()

    async def people(_tier, **kwargs):
        people_kwargs.update(kwargs)
        return ScenarioAccountDto(id="customer-id", email="c@veriprops.io", password="x"), {}

    svc._step = run_inline
    svc._create_people = AsyncMock(side_effect=people)
    svc._verification_terms_version = AsyncMock(return_value="1.0.0")
    svc._verification_service = SimpleNamespace(
        create_draft=AsyncMock(return_value=SimpleNamespace(id="ab" * 16, vid="VP-2026-TEST")),
        submit=AsyncMock(),
        get_owned=AsyncMock(return_value=SimpleNamespace(status=VerificationStatus.SUBMITTED.value)),
    )
    return svc


async def test_customer_phone_is_verified_by_default():
    kwargs: dict = {}
    await _service(kwargs).build(BuildScenarioDto(stage=ScenarioStage.SUBMITTED))
    assert kwargs["customer_phone_verified"] is True


async def test_an_unverified_customer_phone_is_built_for_a_stage_before_payment():
    kwargs: dict = {}
    result = await _service(kwargs).build(
        BuildScenarioDto(stage=ScenarioStage.SUBMITTED, customer_phone_verified=False)
    )
    assert kwargs["customer_phone_verified"] is False
    assert result.status == VerificationStatus.SUBMITTED


@pytest.mark.parametrize("stage", [ScenarioStage.PAID, ScenarioStage.RELEASED])
async def test_a_paying_stage_refuses_an_unverified_customer_phone(stage):
    kwargs: dict = {}
    svc = _service(kwargs)
    with pytest.raises(ValidationException):
        await svc.build(BuildScenarioDto(stage=stage, customer_phone_verified=False))
    svc._create_people.assert_not_called()
