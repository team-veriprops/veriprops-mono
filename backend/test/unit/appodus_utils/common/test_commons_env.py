"""Typed reads of numeric environment settings."""
import pytest

from main.appodus_utils import Utils

_KEY = "APPODUS_TEST_INT_SETTING"


def test_unset_returns_the_default(monkeypatch):
    monkeypatch.delenv(_KEY, raising=False)

    assert Utils.get_int_from_env(_KEY, default=5) == 5


def test_set_value_is_parsed(monkeypatch):
    monkeypatch.setenv(_KEY, " 12 ")

    assert Utils.get_int_from_env(_KEY, default=5) == 12


def test_invalid_value_raises_naming_the_key(monkeypatch):
    monkeypatch.setenv(_KEY, "twelve")

    with pytest.raises(ValueError, match=_KEY):
        Utils.get_int_from_env(_KEY, default=5)
