"""The hourly sweep clears expired key/value entries through the store's own transaction."""
from unittest.mock import AsyncMock, MagicMock

from main.app.jobs.tasks import key_value_sweeps


async def test_sweep_asks_the_store_to_clear_expired_entries(monkeypatch):
    store = MagicMock()
    store.cleanup_expired = AsyncMock()
    monkeypatch.setattr(key_value_sweeps, "di", {key_value_sweeps.KeyValueService: store})

    await key_value_sweeps.check_expired_key_values()

    store.cleanup_expired.assert_awaited_once_with()
