from datetime import datetime

from sqlalchemy import Column, String, LargeBinary

from main.appodus_utils import Utils
from main.appodus_utils.db.models import Base, AutoRepr, Object, UTCDateTime


class KeyValue(Base, AutoRepr):
    __tablename__ = 'key_values'

    key = Column(String(128), primary_key=True, unique=True, index=True, nullable=False)
    value = Column(LargeBinary, nullable=False)
    expires_at = Column(UTCDateTime, nullable=False)

    @property
    def is_expired(self):
        return self.expires_at <= Utils.datetime_now()


class UpsertKeyValue(Object):
    key: str
    value: bytes
    expires_at: datetime
