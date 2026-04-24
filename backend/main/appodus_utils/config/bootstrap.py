from typing import Type, List

from httpx import AsyncClient
from kink import di
from libre_fastapi_jwt import AuthJWTBearer
from redis.asyncio import Redis

from main.appodus_utils.config.logger import LoggerFactory

class BaseDiBootstrap:

    def inject_redis(self):
        """ PLease override in the inheriting class """
        di[Redis] = lambda _di: {}

    def inject_others(self):
        """ PLease implement in the inheriting class """
        pass

    def init(self) -> None:
        self.inject_redis()
        self.inject_others()

        di['logger'] = lambda _di: LoggerFactory().get_logger()
        di[AuthJWTBearer] = lambda _di: AuthJWTBearer()
        di[AsyncClient] = lambda _di: AsyncClient(timeout=30.0, follow_redirects=True)

    @staticmethod
    def register_all_subclasses(base_cls: Type):
        instances = BaseDiBootstrap._get_all_subclasses_instances(base_cls)

        di[List[base_cls]] = instances
        return instances


    @staticmethod
    def register_subclass_if_exists(base_cls: Type):
        instances = BaseDiBootstrap._get_all_subclasses_instances(base_cls)

        if not instances:
            instance = di[base_cls]  # Use DI container to resolve dependencies
            instances.append(instance)

        di[base_cls] = instances[-1]
        return instances

    @staticmethod
    def _get_all_subclasses_instances(base_cls: Type):
        subclasses: List = base_cls.__subclasses__()
        instances = []
        for subclass in subclasses:
            other_subclasses = subclass.__subclasses__()
            if len(other_subclasses) > 0:
                _instances = BaseDiBootstrap._get_all_subclasses_instances(subclass)
                instances.extend(_instances)
            else:
                instance = di[subclass]  # Use DI container to resolve dependencies
                instances.append(instance)

        return instances


base_di_bootstrap = BaseDiBootstrap()
base_di_bootstrap.init()
