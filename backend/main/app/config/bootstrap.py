from main.appodus_utils.config.bootstrap import BaseDiBootstrap

from main.app.config.settings import settings
from kink import di
from redis.asyncio import Redis

class DiBootstrap(BaseDiBootstrap):

    def inject_redis(self):
        """Register the asyncio client `RedisUtils` resolves when REDIS_ENABLED; otherwise keep
        the base's empty registration, which sends `RedisUtils` to the SQL key/value store."""
        if not settings.REDIS_ENABLED:
            super().inject_redis()
            return

        di[Redis] = lambda _di: Redis(
            host=settings.REDIS_HOST,
            port=int(settings.REDIS_PORT or 6379),
            db=int(settings.REDIS_DB or 0),
            password=settings.REDIS_PASSWORD,
            username=settings.REDIS_USERNAME,
        )

    def inject_others(self):
        # Process-singleton real-time emitters (§4.9). Registered as concrete instances
        # (not factories) so every subscriber/publisher shares one broker.
        from main.app.core.realtime.emitter import VerificationEventEmitter
        from main.app.core.realtime.user_emitter import UserEventEmitter
        di[VerificationEventEmitter] = VerificationEventEmitter()
        di[UserEventEmitter] = UserEventEmitter()

        # Process-singleton §4.8 event bus with its standard subscribers registered once.
        from main.app.core.events.bus import EventBus
        from main.app.core.events.subscribers import register_subscribers
        bus = EventBus()
        register_subscribers(bus)
        di[EventBus] = bus


di_bootstrap = DiBootstrap()
di_bootstrap.init()
