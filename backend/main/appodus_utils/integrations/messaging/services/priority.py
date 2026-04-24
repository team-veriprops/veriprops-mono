from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from heapq import heappush, heappop
from typing import Optional

from main.appodus_utils import Utils


class PriorityLevel(IntEnum):
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass(order=True)
class PrioritizedMessage:
    priority: PriorityLevel
    created_at: datetime
    message: object = None


class PriorityQueue:
    def __init__(self):
        self._queue = []

    def add_message(self, message: object, priority: PriorityLevel):
        heappush(self._queue, PrioritizedMessage(
            priority=priority,
            created_at=Utils.datetime_now(),
            message=message
        ))

    def get_next_message(self) -> Optional[object]:
        if self._queue:
            return heappop(self._queue).message
        return None

    def size(self) -> int:
        return len(self._queue)


# Initialize priority queues by channel
priority_queues = {
    "sms": PriorityQueue(),
    "email": PriorityQueue(),
    "whatsapp": PriorityQueue(),
    "push": PriorityQueue(),
    "web_push": PriorityQueue()
}
