from typing import List, Optional, Dict

from main.appodus_utils import Object
from main.appodus_utils.integrations.messaging.providers.push.models import WebPushNotificationRequest, PushNotificationRequest
from main.appodus_utils.integrations.messaging.providers.whatsapp.models import WhatsAppMessageRequest


class BulkPushNotificationRequest(Object):
    requests: List[PushNotificationRequest]
    metadata: Optional[Dict] = None


class BulkWebPushNotificationRequest(Object):
    requests: List[WebPushNotificationRequest]
    metadata: Optional[Dict] = None


class BulkWhatsAppMessageRequest(Object):
    requests: List[WhatsAppMessageRequest]
    metadata: Optional[Dict] = None


class BulkWhatsAppMediaRequest(Object):
    requests: List[Dict]  # List of {'recipient': str, 'media': WhatsAppMedia, ...}
    metadata: Optional[Dict] = None


class BulkWhatsAppInteractiveRequest(Object):
    requests: List[Dict]  # List of {'recipient': str, 'interactive': WhatsAppInteractive, ...}
    metadata: Optional[Dict] = None


class BulkMessageResponse(Object):
    request_count: int
    success_count: int
    failure_count: int
    processing_time: int
    successes: int
    failures: int
