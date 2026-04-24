from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import field_validator

from main.appodus_utils import Object


class WhatsAppMessageType(str, Enum):
    TEXT = "text"
    TEMPLATE = "template"
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"
    AUDIO = "audio"
    INTERACTIVE = "interactive"


class WhatsAppMedia(Object):
    link: Optional[str] = None  # Public URL
    id: Optional[str] = None  # Media ID from WhatsApp
    caption: Optional[str] = None
    filename: Optional[str] = None  # For documents


class WhatsAppButton(Object):
    type: str  # "reply" or "url"
    title: str
    payload: Optional[str] = None  # For reply buttons
    url: Optional[str] = None  # For URL buttons


class WhatsAppSectionRow(Object):
    id: str
    title: str
    description: Optional[str] = None


class WhatsAppSection(Object):
    title: str
    rows: List[WhatsAppSectionRow]


class WhatsAppInteractiveAction(Object):
    button: Optional[str] = None  # For button replies
    buttons: Optional[List[WhatsAppButton]] = None
    sections: Optional[List[WhatsAppSection]] = None


class WhatsAppInteractive(Object):
    type: str  # "list", "button", "product", "product_list"
    header: Optional[Dict[str, Any]] = None
    body: Dict[str, Any]
    footer: Optional[Dict[str, Any]] = None
    action: WhatsAppInteractiveAction


class WhatsAppMessageRequest(Object):
    recipient: str
    message_type: WhatsAppMessageType
    text: Optional[str] = None
    template_name: Optional[str] = None
    language_code: Optional[str] = "en_US"
    components: Optional[List[Dict[str, Any]]] = None
    media: Optional[WhatsAppMedia] = None
    interactive: Optional[WhatsAppInteractive] = None

    @field_validator('components')
    def validate_components(cls, v, values):
        if values.get('message_type') == WhatsAppMessageType.TEMPLATE and not v:
            raise ValueError("Components are required for template messages")
        return v

    @field_validator('media')
    def validate_media(cls, v, values):
        if values.get('message_type') in [
            WhatsAppMessageType.IMAGE,
            WhatsAppMessageType.VIDEO,
            WhatsAppMessageType.AUDIO,
            WhatsAppMessageType.DOCUMENT
        ] and not v:
            raise ValueError("Media is required for media messages")
        return v

    @field_validator('interactive')
    def validate_interactive(cls, v, values):
        if values.get('message_type') == WhatsAppMessageType.INTERACTIVE and not v:
            raise ValueError("Interactive content is required for interactive messages")
        return v
