from abc import ABC, abstractmethod
from typing import Optional

from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.db.types.money import Money
from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageProviderName
from main.appodus_utils.integrations.messaging.providers.push.models import PushProviderType


class IMessageProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> MessageProviderName:
        pass

    @property
    @abstractmethod
    def supported_channels(self) -> list[MessageChannel]:
        pass

    @abstractmethod
    async def get_cost(self, message_id: str) -> Money:
        pass

    @abstractmethod
    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        pass

    @abstractmethod
    async def get_message_status(self, message_id: str) -> Optional[str]:
        """Return the provider's raw status string, or None if polling is unsupported."""
        pass


class PushNotificationProvider(IMessageProvider):
    @property
    @abstractmethod
    def push_provider_type(self) -> PushProviderType:
        pass
