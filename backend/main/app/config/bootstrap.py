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
        # Process-singleton real-time emitter (§4.9). Registered as a concrete
        # instance (not a factory) so every subscriber/publisher shares one broker.
        from main.app.core.realtime.emitter import VerificationEventEmitter
        di[VerificationEventEmitter] = VerificationEventEmitter()


di_bootstrap = DiBootstrap()
di_bootstrap.init()
