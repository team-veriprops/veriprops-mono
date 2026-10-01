"""Service-account credential loading (Firebase push, Google Drive).

Deployed environments get the key as base64 JSON from Doppler; a developer may keep a
gitignored key file instead. With neither, the caller learns that the integration is not
configured, and startup is never broken by it.
"""
import base64
import json

import pytest

from main.appodus_utils.config.service_account import load_service_account_info
from main.appodus_utils.config.settings import SECRET_PLACEHOLDER

INFO = {"type": "service_account", "project_id": "veriprops-test", "client_email": "svc@test"}


def _b64(info: dict) -> str:
    return base64.b64encode(json.dumps(info).encode()).decode()


def test_the_doppler_value_wins_over_a_local_file(tmp_path):
    local = tmp_path / "key.json"
    local.write_text(json.dumps({**INFO, "project_id": "from-file"}))

    assert load_service_account_info(_b64(INFO), str(local)) == INFO


def test_a_line_wrapped_doppler_value_decodes():
    """GNU `base64` wraps at 76 columns, and a pasted secret often carries a trailing newline."""
    encoded = _b64({**INFO, "private_key_id": "x" * 120})
    wrapped = chr(10).join(encoded[i:i + 76] for i in range(0, len(encoded), 76)) + chr(10)

    assert load_service_account_info(wrapped, None)["private_key_id"] == "x" * 120


def test_a_local_file_is_the_fallback(tmp_path):
    local = tmp_path / "key.json"
    local.write_text(json.dumps(INFO))

    assert load_service_account_info(None, str(local)) == INFO


@pytest.mark.parametrize("encoded", [None, "", SECRET_PLACEHOLDER])
def test_nothing_configured_is_none(encoded, tmp_path):
    assert load_service_account_info(encoded, str(tmp_path / "missing.json")) is None
    assert load_service_account_info(encoded, None) is None


def test_a_malformed_doppler_value_fails_loudly_without_echoing_it():
    with pytest.raises(ValueError) as caught:
        load_service_account_info("bm90LWpzb24=", None)  # base64 of "not-json"

    assert "bm90LWpzb24" not in str(caught.value)
