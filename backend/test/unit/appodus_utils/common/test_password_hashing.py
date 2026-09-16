"""Async password hashing — Argon2 is CPU-bound, so request paths must not run it on the event loop.

A synchronous hash inside an async handler stalls every other request the process is serving —
including the silent session refresh of every other signed-in user — for the length of the hash.
"""
from __future__ import annotations

import asyncio

from main.appodus_utils import Utils

PASSWORD = "Correct-Horse-1"


class TestAsyncPasswordHashing:
    async def test_a_hash_verifies_against_its_own_password_only(self):
        hashed = await Utils.hash_password(PASSWORD)

        assert hashed != PASSWORD
        assert await Utils.check_password(PASSWORD, hashed)
        assert not await Utils.check_password("wrong-password", hashed)

    async def test_empty_inputs_never_verify(self):
        hashed = await Utils.hash_password(PASSWORD)

        assert not await Utils.check_password("", hashed)
        assert not await Utils.check_password(PASSWORD, "")

    async def test_hashing_leaves_the_event_loop_free_to_serve_other_work(self):
        ticks = 0

        async def other_request():
            nonlocal ticks
            while True:
                ticks += 1
                await asyncio.sleep(0.002)

        task = asyncio.create_task(other_request())
        try:
            await Utils.hash_password(PASSWORD)
            await Utils.check_password(PASSWORD, await Utils.hash_password(PASSWORD))
        finally:
            task.cancel()

        # Run synchronously, the hashes would starve the concurrent coroutine entirely; offloaded,
        # it keeps getting scheduled while they run.
        assert ticks >= 3
