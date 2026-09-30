"""AdminNoteRepo — the admin detail lists a note added earlier in the same request (§6.3).

Sessions run with autoflush off, so a note created in the add-note request stays pending until
flushed; listing without flushing returned the detail without the note the admin had just added.
"""
from unittest.mock import AsyncMock, MagicMock

from main.app.domain.verification.admin_note.repo import AdminNoteRepo
from main.appodus_utils.db.session import db_session_ctx


async def test_listing_flushes_pending_notes_before_reading():
    order = []
    session = MagicMock()
    session.flush = AsyncMock(side_effect=lambda: order.append("flush"))
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=lambda stmt: order.append("select") or result)
    token = db_session_ctx.set(session)
    try:
        repo = object.__new__(AdminNoteRepo)
        await repo.list_for_verification("01a0f380183d78d184db656d2b5bca5f")
    finally:
        db_session_ctx.reset(token)

    assert order == ["flush", "select"]
