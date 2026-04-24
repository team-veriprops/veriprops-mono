from typing import Optional

from main.appodus_utils import Object


class MessageResponse(Object):
    ai: str
    user: Optional[str] = None
