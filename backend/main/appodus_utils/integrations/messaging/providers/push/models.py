from enum import Enum
from typing import Optional, List, Dict, Any

from main.appodus_utils import Object


class PushProviderType(str, Enum):
    FIREBASE = "firebase"
    APNS = "apns"  # Apple Push Notification Service
    WEB_PUSH = "web_push"


class PushNotificationPayload(Object):
    title: str
    body: str
    image_url: Optional[str] = None
    deep_link: Optional[str] = None
    data: Optional[Dict[str, Any]] = None  # For custom key-value pairs
    priority: str = "normal"  # 'normal' or 'high'
    ttl: Optional[int] = None  # Time to live in seconds


class PushNotificationRecipient(Object):
    device_tokens: List[str]  # For mobile apps
    platform: str  # 'ios', 'android', 'web'
    user_id: Optional[str] = None
    web_push_subscription: Optional[Dict] = None  # For web push


class WebPushNotificationPayload(Object):
    title: str
    body: str
    icon: Optional[str] = None
    image: Optional[str] = None
    badge: Optional[str] = None
    vibrate: Optional[List[int]] = None
    timestamp: Optional[int] = None
    actions: Optional[List[Dict[str, str]]] = None
    data: Optional[Dict] = None
    require_interaction: Optional[bool] = False
    tag: Optional[str] = None
    silent: Optional[bool] = False


class WebPushNotificationRecipient(Object):
    endpoint: str  # The push subscription endpoint
    keys: Dict[str, str]  # auth and p256dh keys
    user_id: Optional[str] = None
    browser: Optional[str] = None


class PushNotificationRequest(Object):
    recipient: PushNotificationRecipient
    payload: PushNotificationPayload


class WebPushNotificationRequest(Object):
    recipient: WebPushNotificationRecipient
    payload: WebPushNotificationPayload
