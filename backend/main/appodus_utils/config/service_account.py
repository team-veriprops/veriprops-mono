"""Google service-account credentials, shared by Firebase push and Google Drive.

Deployed environments receive the key JSON base64-encoded in a secret env var injected by
Doppler, so no key file is ever committed or bundled. A developer may instead keep a
gitignored key file at the configured path. With neither set, the integration reports that
it is not configured, and the caller decides what that means.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
from typing import Optional

from main.appodus_utils.config.settings import SECRET_PLACEHOLDER


def load_service_account_info(encoded_json: Optional[str], file_path: Optional[str]) -> Optional[dict]:
    """The service-account key as a dict: the base64 secret first, then the local file.

    Returns ``None`` when neither is configured. A secret that is set but does not decode to
    JSON raises ``ValueError`` without repeating its contents, because it is a credential.
    """
    if encoded_json and encoded_json != SECRET_PLACEHOLDER:
        # GNU `base64` wraps at 76 columns and a pasted secret often ends in a newline.
        compact = "".join(encoded_json.split())
        try:
            return json.loads(base64.b64decode(compact, validate=True))
        except (binascii.Error, ValueError):
            raise ValueError("The service-account secret is not base64-encoded JSON.") from None
    if file_path and os.path.isfile(file_path):
        with open(file_path, encoding="utf-8") as key_file:
            return json.load(key_file)
    return None
