"""The user and message existence validators — what a missing or taken record answers with.

A missing user or message is a 404 naming the resource, never the raw id; a signup with an
email already on an account is a 409.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from main.app.domain.message.validator import MessageValidator
from main.app.domain.user.validator import UserValidator
from main.appodus_utils.exception.exceptions import (
    ResourceNotFoundException,
    UserAlreadyExistsException,
    UserNotFoundException,
)


def _user_validator(exists=True, by_email=None):
    repo = MagicMock(exists_by_id=AsyncMock(return_value=exists), get_by_email=AsyncMock(return_value=by_email))
    return UserValidator(user_repo=repo)


def _message_validator(exists=True):
    return MessageValidator(message_repo=MagicMock(exists_by_id=AsyncMock(return_value=exists)))


class TestUserValidator:
    async def test_an_existing_user_passes(self):
        await _user_validator().should_exist_by_id("u1")

    async def test_a_missing_user_is_a_404(self):
        with pytest.raises(UserNotFoundException) as err:
            await _user_validator(exists=False).should_exist_by_id("u1")
        assert err.value.status_code == 404

    async def test_an_unused_email_passes(self):
        await _user_validator().should_not_exist_by_email("new@example.com")

    async def test_an_email_already_on_an_account_is_a_409(self):
        with pytest.raises(UserAlreadyExistsException) as err:
            await _user_validator(by_email=SimpleNamespace(id="u1")).should_not_exist_by_email("ada@example.com")
        assert err.value.status_code == 409


class TestMessageValidator:
    async def test_an_existing_message_passes(self):
        await _message_validator().should_exist_by_id("m1")

    async def test_a_missing_message_is_a_404_naming_the_resource_not_the_id(self):
        with pytest.raises(ResourceNotFoundException) as err:
            await _message_validator(exists=False).should_exist_by_id("m-secret-id")
        assert err.value.status_code == 404
        assert err.value.message == "Message not found"
