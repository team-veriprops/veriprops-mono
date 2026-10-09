"""The broadcasts list reports real page metadata, so the admin table can page past the first
page (it once sent a field `PaginationMeta` does not have, and Next stayed disabled)."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from main.app.domain.broadcast import controller
from main.app.domain.broadcast.models import BroadcastAudience, BroadcastStatus


def _broadcast(i: int):
    return SimpleNamespace(
        id=f"b{i}", audience=BroadcastAudience.ALL.value, subject="s", body="b",
        status=BroadcastStatus.DRAFT.value, scheduled_at=None, sent_at=None,
        recipient_count=0, recipients_enqueued=0, date_created=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )


async def test_the_list_carries_total_and_next_page():
    rows = [_broadcast(i) for i in range(10)]
    with patch.object(controller.broadcast_service, "list_page", AsyncMock(return_value=(rows, 23))):
        response = await controller.list_broadcasts(page=0, page_size=10, status=None, _admin_id="admin-1")

    meta = response.data.meta
    assert (meta.total, meta.total_pages, meta.next_page, meta.prev_page, meta.count) == (23, 3, 1, None, 10)
