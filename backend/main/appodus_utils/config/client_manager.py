import atexit, asyncio

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
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(httpx_client.aclose())
            else:
                loop.run_until_complete(httpx_client.aclose())
        except Exception:
            pass
