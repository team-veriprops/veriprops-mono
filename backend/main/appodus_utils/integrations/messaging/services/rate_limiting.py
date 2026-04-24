import asyncio
import logging
from collections import defaultdict
from datetime import timedelta
from typing import Optional

from kink import di, inject

from main.app.config.settings import settings
from main.appodus_utils.integrations.exception.exceptions import IntegrationRateLimitException
from main.appodus_utils import Utils

logger: logging.Logger = di['logger']


@inject
class RateLimiter:
    def __init__(self):
        self.limits = defaultdict(lambda: {
            "count": 0,
            "last_reset": Utils.datetime_now(),
            "lock": asyncio.Lock()
        })
        self.default_limits = {
            "sms": {"limit": 100, "window": 60},
            "email": {"limit": 1000, "window": 60},
            "whatsapp": {"limit": 50, "window": 60},
            "push": {"limit": 500, "window": 60},
            "web_push": {"limit": 500, "window": 60}
        }

    async def check_limit(
            self,
            key: str,
            limit: Optional[int] = None,
            window: Optional[int] = None
    ) -> bool:
        """Check if request is allowed, raises RateLimitExceeded if not"""
        if settings.DISABLE_RATE_LIMITING:
            return True

        limit_config = self._get_limit_config(key, limit, window)
        async with self.limits[key]["lock"]:
            self._maybe_reset_counter(key, limit_config["window"])

            if self.limits[key]["count"] >= limit_config["limit"]:
                reset_in = (self.limits[key]["last_reset"] +
                            timedelta(seconds=limit_config["window"]) -
                            Utils.datetime_now())
                raise IntegrationRateLimitException(key, Utils.datetime_now() + reset_in)

            self.limits[key]["count"] += 1
            # TODO: Fix
            # metrics_manager.rate_limit_usage.labels(
            #     key=key
            # ).set(self.limits[key]["count"] / limit_config["limit"])
            return True

    def _get_limit_config(self, key: str, limit: Optional[int], window: Optional[int]):
        """Get limit configuration from defaults or parameters"""
        if limit is not None and window is not None:
            return {"limit": limit, "window": window}

        # Extract channel from key if formatted as "channel:tenant"
        channel = key.split(":")[0] if ":" in key else key
        return self.default_limits.get(channel, {"limit": 100, "window": 60})

    def _maybe_reset_counter(self, key: str, window: int):
        """Reset counter if window has elapsed"""
        now = Utils.datetime_now()
        if (now - self.limits[key]["last_reset"]).total_seconds() >= window:
            self.limits[key]["count"] = 0
            self.limits[key]["last_reset"] = now


class Throttler:
    """A rate limiter that enforces minimum intervals between operations.

    Implements both direct throttling and async context manager interfaces to
    control the rate of operations. Uses a semaphore to limit concurrent
    operations and enforces time intervals between executions.

    Typical usage examples:

        # As async context manager (recommended)
        async with throttler:
            await make_request()

        # Direct throttling call
        await throttler.throttle()
        await make_request()

    Attributes:
        rps_limit (int): Maximum allowed requests per second (default: 10)
        min_interval (float): Automatically calculated minimum time between
                             operations (1/rps_limit seconds)
    """

    def __init__(self, rps_limit: int = 10) -> None:
        """Initialize the throttler with a requests-per-second limit.

        Args:
            rps_limit: Maximum allowed operations per second. Must be positive.
                      Determines both concurrency and timing constraints.

        Raises:
            ValueError: If rps_limit is not a positive integer
        """
        if rps_limit <= 0:
            raise ValueError("rps_limit must be positive")

        self.semaphore = asyncio.Semaphore(rps_limit)
        self.last_request_time: Optional[float] = None
        self.min_interval: float = 1.0 / rps_limit

    async def __aenter__(self) -> "Throttler":
        """Enter the throttler context.

        Waits until the operation can proceed based on rate limits.

        Returns:
            The throttler instance itself
        """
        await self.throttle()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the throttler context.

        Args:
            exc_type: Exception type if any
            exc_val: Exception value if any
            exc_tb: Exception traceback if any
        """
        pass  # Context manager cleanup (no action needed)

    async def throttle(self, min_interval: Optional[float] = None) -> None:
        """Enforce rate limiting before an operation.

        Args:
            min_interval: Optional override of minimum time between operations.
                         If None, uses the automatically calculated interval.

        Note:
            - Uses asyncio.Semaphore to limit concurrent operations
            - Enforces time interval between operations
            - Thread-safe for async operations
        """
        interval = min_interval or self.min_interval
        async with self.semaphore:
            now = asyncio.get_event_loop().time()
            if self.last_request_time is not None:
                elapsed = now - self.last_request_time
                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)
            self.last_request_time = now
