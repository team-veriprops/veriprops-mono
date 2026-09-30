import atexit
import asyncio

from httpx import AsyncClient
from kink import di

from main.appodus_utils.db.session import init_db_engine_and_session, close_db_engine

httpx_client: AsyncClient = di[AsyncClient]

class ClientStateManager:

    async def init_clients(self):
        init_db_engine_and_session()

    async def close_clients(self):
        self._close_httpx_client()
        await close_db_engine()

    @staticmethod
    @atexit.register
    def _close_httpx_client():
        """Close the shared HTTP client: on the app's loop during shutdown, or on a fresh one
        at interpreter exit, when no loop is running."""
        try:
            asyncio.get_running_loop().create_task(httpx_client.aclose())
            return
        except RuntimeError:
            pass  # no running loop: this is the atexit call
        try:
            asyncio.run(httpx_client.aclose())
        except Exception as exc:
            # At exit the client's own loop is often gone already; nothing is left to leak.
            di["logger"].debug(f"Closing the shared HTTP client at exit: {exc!r}")
