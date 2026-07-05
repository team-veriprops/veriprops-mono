import redis
from main.appodus_utils.config.bootstrap import BaseDiBootstrap

from main.app.config.settings import settings
from kink import di
from redis import Redis

class DiBootstrap(BaseDiBootstrap):

    def inject_redis(self):
        di[Redis] = lambda _di: redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            username=settings.REDIS_USERNAME
        ) if settings.REDIS_ENABLED else {}

    def inject_others(self):
        # Process-singleton real-time emitters (§4.9). Registered as concrete instances
        # (not factories) so every subscriber/publisher shares one broker.
        from main.app.core.realtime.emitter import VerificationEventEmitter
        from main.app.core.realtime.user_emitter import UserEventEmitter
        di[VerificationEventEmitter] = VerificationEventEmitter()
        di[UserEventEmitter] = UserEventEmitter()


di_bootstrap = DiBootstrap()
di_bootstrap.init()
