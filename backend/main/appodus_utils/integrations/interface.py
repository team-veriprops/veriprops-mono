import json
import time
from abc import ABC, abstractmethod
from logging import Logger
from typing import Dict, List, Callable, Optional

from httpx import QueryParams
from kink import di
from starlette.responses import Response, RedirectResponse

from main.app.config.settings import IntegratedPlatform
from main.app.domain.webhook.callback.model import QueryCallbackDto
from main.appodus_utils.exception.exceptions import UnauthorizedException

logger: Logger = di['logger']

class IEventSubscriber(ABC):
    @abstractmethod
    def update(self, payload: Dict) -> None:
        pass


class IWebhookHandler(ABC):

    @property
    @abstractmethod
    def platform(self) -> IntegratedPlatform:
        pass

    @abstractmethod
    async def webhook_replay_handler(self, callback: QueryCallbackDto) -> None:
        pass

    @abstractmethod
    async def validate_signature(self, body: bytes, headers: Dict) -> bool:
        pass

    @abstractmethod
    async def handle_redirect(self, payload: QueryParams, headers: Dict, response: Response) -> Optional[
        RedirectResponse]:
        pass

    @abstractmethod
    async def verify_webhook(self, payload: QueryParams, headers: Dict):
        pass

    @abstractmethod
    async def handle_webhook(self, body: bytes, headers: Dict) -> None:
        pass


class BaseWebhookHandler(IWebhookHandler):
    def __init__(self, platform_secret: str):
        self.platform_secret = platform_secret
        self._observers: List[IEventSubscriber] = []

    def attach(self, observer: IEventSubscriber) -> None:
        self._observers.append(observer)

    def _notify_observers(self, payload: Dict) -> None:
        for observer in self._observers:
            observer.update(payload)

    @staticmethod
    def _log_event(body: bytes, headers: Dict) -> None:
        logger.info(f"Webhook processing event, payload: {body}")
        logger.info(f"Webhook processing event, header: {headers}")

    @staticmethod
    async def _retry_logic(action: Callable, max_retries: int = 3) -> None:
        for attempt in range(max_retries):
            try:
                return await action()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt
                logger.warning(f"Attempt {attempt + 1} failed. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        return None

    async def handle_redirect(self, payload: QueryParams, headers: Dict, response: Response) -> Optional[RedirectResponse]:

        async def _process():
            logger.info(f"Request body: {payload}")
            processed_data = await self._process_handle_redirect_payload(payload, headers, response)
            return processed_data

        return await self._retry_logic(_process)

    async def verify_webhook(self, payload: QueryParams, headers: Dict) -> None:

        async def _process():
            logger.info(f"Request body: {payload}")
            return await self._process_verify_webhook_payload(payload)

        return await self._retry_logic(_process)

    async def handle_webhook(self, body: bytes, headers: Dict) -> None:
        self._log_event(body, headers)
        if not (await self.validate_signature(body, headers)):
            raise UnauthorizedException("Invalid signature")

        async def _process():
            logger.info(f"Request body: {body}")
            payload = json.loads(body)
            processed_data = await self._process_handle_webhook_payload(payload)
            self._notify_observers(processed_data)
            return processed_data

        return await self._retry_logic(_process)

    @abstractmethod
    async def _process_handle_redirect_payload(self, payload: QueryParams, headers: Dict, response: Response) -> Optional[RedirectResponse]:
        pass

    @abstractmethod
    async def _process_verify_webhook_payload(self, payload: QueryParams) -> Dict:
        pass

    @abstractmethod
    async def _process_handle_webhook_payload(self, payload: Dict) -> Dict:
        pass
