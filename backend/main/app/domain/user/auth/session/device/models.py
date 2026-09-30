from sqlalchemy import Column, String

from main.appodus_utils import BaseEntity
from main.appodus_utils.db.models import UTCDateTime, JSONB_VARIANT


class Device(BaseEntity):
    """A user's push-capable device. `UserRepo.get_user_contact` reads a user's devices to
    address push.

    TODO(gap): Push delivery — nothing registers devices until push ships — PRD "Known Gaps & Roadmap".
    """
    __tablename__ = 'devices'
    user_id = Column(String(36), nullable=False, index=True)
    device_id = Column(String(36), nullable=False)
    push_provider_type = Column(String(20), nullable=False)
    push_token = Column(JSONB_VARIANT, nullable=False)
    last_active = Column(UTCDateTime, nullable=False)
