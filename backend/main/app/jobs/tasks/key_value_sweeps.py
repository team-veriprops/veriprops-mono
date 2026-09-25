"""Expired-entry cleanup for the SQL key/value store.

Reads already ignore expired entries, and remove the one they touch. This sweep clears the rest
(spent OTP codes, lapsed rate-limit windows, abandoned OAuth states) so the table stays small.
There is no job wrapper: `KeyValueService` writes commit on their own (INDEPENDENT), so a
wrapper session would only hold a connection it never uses.
"""
from __future__ import annotations

from kink import di

from main.appodus_utils.domain.key_value.service import KeyValueService


async def check_expired_key_values() -> None:
    await di[KeyValueService].cleanup_expired()
