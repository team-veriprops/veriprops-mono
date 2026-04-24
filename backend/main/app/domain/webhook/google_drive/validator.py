from kink import inject

from main.app.domain.webhook.google_drive.repo import GoogleDriveWebhookSubscriptionRepo
from main.appodus_utils.exception.exceptions import EntityNotFoundException


@inject
class GoogleDriveWebhookSubscriptionValidator:
    def __init__(self, g_drive_subscription_repo: GoogleDriveWebhookSubscriptionRepo):
        self._g_drive_subscription_repo = g_drive_subscription_repo

    async def should_exist_by_id(self, _id: str):
        if not (await self._g_drive_subscription_repo.exists_by_id(_id)):
            raise EntityNotFoundException("GoogleDriveWebhookSubscription", _id)
