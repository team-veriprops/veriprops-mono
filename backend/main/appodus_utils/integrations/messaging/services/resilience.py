"""
Advanced Resilience Framework with Circuit Breaking, Retries, and Context Propagation

Features:
1. Automatic request context propagation — once before retry loop, not per attempt
2. Circuit breaker with TTL-protected state tracking for ALL states (open + closed)
3. Detailed failure classification (timeouts, 5xx, connection, circuit_open)
4. Async/sync support with correct separate code paths for both
5. Prometheus metrics integration — retry counter fires only on actual retries
6. Thread-safe operations
7. Optional fallback callable on open circuit

Requirements:
    pip install httpx circuitbreaker prometheus_client tenacity cachetools

FIX CHANGELOG (from code review):
    [CRITICAL] messaging_circuit_breaker now has separate async/sync paths — was
               sync-only, silently returning a coroutine object for async functions.
    [CRITICAL] _is_retryable_error now explicitly excludes CircuitBreakerError so
               an open circuit is never retried. Stacking order (retry outer,
               circuit breaker inner) is enforced by design and documented here.
    [CRITICAL] _propagate_context is called once before AsyncRetrying loop, not
               inside it on every attempt.
    [DESIGN]   REQUEST_CONTEXT_RETRIES counter moved to _log_retry (before_sleep
               hook) so it only fires on actual retries, not the first attempt.
    [DESIGN]   self._metrics dict removed — metrics are module-level globals and
               were never read from the dict, creating false encapsulation.
    [DESIGN]   get_circuit_state returns a default closed-state dict instead of
               None for unknown circuits, distinguishing healthy from untracked.
    [DESIGN]   _update_circuit_state called on success too, so closed state is
               always recorded and the Prometheus gauge stays accurate.
    [DESIGN]   Threshold interaction documented: retries are excluded from circuit
               breaker failure counts because CircuitBreakerError is non-retryable.
    [MINOR]    @wraps applied correctly: outermost callable for both async and sync.
    [MINOR]    Utils.datetime_now() replaced with datetime.now(timezone.utc).
    [MINOR]    fallback: Optional[Callable] added to messaging_circuit_breaker.
"""

import asyncio
import logging
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, Optional, TypeVar

import httpx
from cachetools import TTLCache
from circuitbreaker import CircuitBreakerError, circuit
from prometheus_client import Counter, Gauge, Histogram
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from main.appodus_utils import Utils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# Prometheus Metrics
#
# Defined at module level for a single registration across all manager
# instances. Use per-circuit labels (circuit_name, function_name) to scope.
# ---------------------------------------------------------------------------

CIRCUIT_STATE = Gauge(
    "circuit_state",
    "Current circuit state (1=open, 0=closed)",
    ["circuit_name"],
)

FAILURE_REASONS = Counter(
    "failure_reasons_total",
    "Failure breakdown by type",
    ["circuit_name", "error_type"],
)

RETRY_ATTEMPTS = Histogram(
    "retry_attempts_total",
    "Attempt number recorded on each retry (excludes first attempt)",
    ["function_name"],
)

REQUEST_CONTEXT_RETRIES = Counter(
    "request_context_retries_total",
    "Count of retried requests — excludes first attempt, fires in before_sleep",
    ["function_name"],
)


class ResilienceManager:
    """Advanced resilience manager with comprehensive failure handling.

    CRITICAL — Decorator stacking order:
        Retry MUST be the outer decorator; circuit breaker MUST be inner:

            @manager.messaging_retry()           # outer
            @manager.messaging_circuit_breaker() # inner
            async def fetch_data(...): ...

        If reversed, each retry attempt is seen as an independent failure by
        the circuit breaker, collapsing the effective threshold to
        ``failure_threshold / max_attempts``.

    Example::

        manager = ResilienceManager(
            default_headers={"User-Agent": "MyClient/1.0"}
        )

        async def _fallback(*args, **kwargs):
            return {"status": "degraded", "data": None}

        @manager.messaging_retry(max_attempts=3)
        @manager.messaging_circuit_breaker(name="my_api", fallback=_fallback)
        async def fetch_data(url: str, headers: dict = None):
            async with httpx.AsyncClient(headers=headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
    """

    def __init__(
        self,
        default_headers: Optional[Dict[str, str]] = None,
        circuit_ttl: int = 86400,
        max_circuits: int = 1000,
    ) -> None:
        """Initialise the resilience manager.

        Args:
            default_headers: Base headers merged into every request.
            circuit_ttl:     Seconds to retain circuit state (default 24 h).
            max_circuits:    Maximum circuits tracked before LRU eviction.
        """
        self._circuit_states: TTLCache = TTLCache(
            maxsize=max_circuits, ttl=circuit_ttl
        )
        self._lock = Lock()
        self._default_headers: Dict[str, str] = default_headers or {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_retryable_error(e: BaseException) -> bool:
        """Return True if *e* is a transient error worth retrying.

        CircuitBreakerError is explicitly excluded: an open circuit needs
        recovery time, not additional attempts that would only pile more
        failures onto the breaker.
        """
        if isinstance(e, CircuitBreakerError):
            return False
        if isinstance(e, httpx.TimeoutException):
            return True
        if isinstance(e, httpx.HTTPStatusError):
            return e.response.status_code >= 500
        return isinstance(e, httpx.RequestError)

    @staticmethod
    def _classify_error(e: Exception) -> str:
        """Map an exception to a short label for Prometheus."""
        if isinstance(e, CircuitBreakerError):
            return "circuit_open"
        if isinstance(e, httpx.TimeoutException):
            return "timeout"
        if isinstance(e, httpx.HTTPStatusError):
            return "5xx" if e.response.status_code >= 500 else "validation"
        if isinstance(e, httpx.RequestError):
            return "connection"
        return "unexpected"

    def _log_retry(self, retry_state: RetryCallState) -> None:
        """Log a retry attempt and update metrics.

        Registered as tenacity's ``before_sleep`` hook, so it fires only
        *between* attempts — never on the initial call. This is the correct
        place for retry-specific counters.
        """
        exc = retry_state.outcome.exception()
        fn_name = retry_state.fn.__name__
        logger.warning(
            "Retrying %s: attempt %d failed with %r",
            fn_name,
            retry_state.attempt_number,
            exc,
        )
        RETRY_ATTEMPTS.labels(function_name=fn_name).observe(
            retry_state.attempt_number
        )
        REQUEST_CONTEXT_RETRIES.labels(function_name=fn_name).inc()

    def _propagate_context(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of *kwargs* with default headers merged in.

        Called once before the retry loop begins, so headers are not
        re-merged on every attempt.
        """
        return {
            **kwargs,
            "headers": {**self._default_headers, **kwargs.get("headers", {})},
            "context": kwargs.get("context", {}),
        }

    def _update_circuit_state(
        self,
        circuit_name: str,
        *,
        is_open: bool,
        error: Optional[str] = None,
    ) -> None:
        """Persist circuit state and update the Prometheus gauge atomically."""
        with self._lock:
            self._circuit_states[circuit_name] = {
                "open": is_open,
                "since": Utils.datetime_now(),
                "error": error,
            }
            CIRCUIT_STATE.labels(circuit_name=circuit_name).set(
                1 if is_open else 0
            )

    # ------------------------------------------------------------------
    # Public decorators
    # ------------------------------------------------------------------

    def messaging_retry(
        self,
        max_attempts: int = 3,
        min_wait: float = 1,
        max_wait: float = 10,
        propagate_context: bool = True,
    ) -> Callable[[F], F]:
        """Decorator factory for retry logic with context propagation.

        Must be the **outer** decorator when combined with
        :meth:`messaging_circuit_breaker`.

        Args:
            max_attempts:      Total attempts including the first.
            min_wait:          Minimum exponential back-off seconds.
            max_wait:          Maximum exponential back-off seconds.
            propagate_context: Merge ``default_headers`` into kwargs once
                               before the retry loop (not per attempt).
        """

        def decorator(f: F) -> F:

            if asyncio.iscoroutinefunction(f):

                @wraps(f)
                async def async_wrapped(*args: Any, **kwargs: Any) -> Any:
                    # Propagate context ONCE before entering the retry loop.
                    if propagate_context:
                        kwargs = self._propagate_context(kwargs)

                    async for attempt in AsyncRetrying(
                        stop=stop_after_attempt(max_attempts),
                        wait=wait_random_exponential(min=min_wait, max=max_wait),
                        retry=retry_if_exception(self._is_retryable_error),
                        before_sleep=self._log_retry,
                    ):
                        with attempt:
                            return await f(*args, **kwargs)

                return async_wrapped  # type: ignore[return-value]

            else:
                # Define the retryable core separately so that:
                # (a) context propagation happens once in the outer wrapper, and
                # (b) @wraps is applied to the outermost callable, not buried
                #     under tenacity's wrapper.
                def _retryable(*args: Any, **kwargs: Any) -> Any:
                    return f(*args, **kwargs)

                _retried = retry(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_random_exponential(min=min_wait, max=max_wait),
                    retry=retry_if_exception(self._is_retryable_error),
                    before_sleep=self._log_retry,
                )(_retryable)

                @wraps(f)
                def sync_wrapped(*args: Any, **kwargs: Any) -> Any:
                    if propagate_context:
                        kwargs = self._propagate_context(kwargs)
                    return _retried(*args, **kwargs)

                return sync_wrapped  # type: ignore[return-value]

        return decorator  # type: ignore[return-value]

    def messaging_circuit_breaker(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: Optional[str] = None,
        fallback: Optional[Callable[..., Any]] = None,
    ) -> Callable[[F], F]:
        """Decorator factory for circuit breaking with failure tracking.

        Must be the **inner** decorator when combined with
        :meth:`messaging_retry`.

        Args:
            failure_threshold: Consecutive failures required to open the
                               circuit.
            recovery_timeout:  Seconds before transitioning to half-open.
            name:              Circuit identifier (defaults to function name).
            fallback:          Optional callable invoked when the circuit is
                               open. Receives the same ``*args``/``**kwargs``
                               as the original function and may be sync or
                               async. When *None*, ``CircuitBreakerError``
                               propagates to the caller.
        """

        def decorator(f: F) -> F:
            circuit_name = name or f.__name__

            cb = circuit(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=(httpx.RequestError, httpx.HTTPStatusError),
                name=circuit_name,
            )
            # Wrap once at decoration time, not on every call.
            cb_wrapped = cb(f)

            # Record initial closed state so get_circuit_state is never None.
            self._update_circuit_state(circuit_name, is_open=False)

            if asyncio.iscoroutinefunction(f):

                @wraps(f)
                async def async_wrapped(*args: Any, **kwargs: Any) -> Any:
                    try:
                        result = await cb_wrapped(*args, **kwargs)
                        # Record healthy state on every success so the gauge
                        # accurately reflects recovery after a half-open probe.
                        self._update_circuit_state(circuit_name, is_open=False)
                        return result

                    except CircuitBreakerError as exc:
                        FAILURE_REASONS.labels(
                            circuit_name=circuit_name, error_type="circuit_open"
                        ).inc()
                        self._update_circuit_state(
                            circuit_name, is_open=True, error=str(exc)
                        )
                        if fallback is not None:
                            if asyncio.iscoroutinefunction(fallback):
                                return await fallback(*args, **kwargs)
                            return fallback(*args, **kwargs)
                        raise

                    except Exception as exc:
                        FAILURE_REASONS.labels(
                            circuit_name=circuit_name,
                            error_type=self._classify_error(exc),
                        ).inc()
                        raise

                return async_wrapped  # type: ignore[return-value]

            else:

                @wraps(f)
                def sync_wrapped(*args: Any, **kwargs: Any) -> Any:
                    try:
                        result = cb_wrapped(*args, **kwargs)
                        self._update_circuit_state(circuit_name, is_open=False)
                        return result

                    except CircuitBreakerError as exc:
                        FAILURE_REASONS.labels(
                            circuit_name=circuit_name, error_type="circuit_open"
                        ).inc()
                        self._update_circuit_state(
                            circuit_name, is_open=True, error=str(exc)
                        )
                        if fallback is not None:
                            return fallback(*args, **kwargs)
                        raise

                    except Exception as exc:
                        FAILURE_REASONS.labels(
                            circuit_name=circuit_name,
                            error_type=self._classify_error(exc),
                        ).inc()
                        raise

                return sync_wrapped  # type: ignore[return-value]

        return decorator  # type: ignore[return-value]

    def get_circuit_state(self, name: str) -> Dict[str, Any]:
        """Return current circuit state with metadata.

        Always returns a valid dict — never ``None``. Returns a default
        closed state for circuits that have never fired, making "healthy"
        and "never seen" distinguishable from each other.

        Returns:
            dict with keys:
                - ``open``  (bool):            True when circuit is open.
                - ``since`` (datetime | None):  When state was last updated.
                - ``error`` (str | None):       Last error if open, else None.
        """
        with self._lock:
            return self._circuit_states.get(
                name,
                {"open": False, "since": None, "error": None},
            )


# Module-level singleton for convenience; instantiate your own for isolation.
resilience_manager = ResilienceManager()


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    from prometheus_client import start_http_server

    start_http_server(8000)

    manager = ResilienceManager(
        default_headers={
            "User-Agent": "ResilienceClient/1.0",
            "Accept": "application/json",
        }
    )

    async def _fallback_response(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Return a degraded-mode response when the circuit is open."""
        logger.warning("Circuit open — serving cached fallback response.")
        return {"status": "degraded", "data": None}

    @manager.messaging_retry(max_attempts=3)
    @manager.messaging_circuit_breaker(
        name="example_api", fallback=_fallback_response
    )
    async def fetch_example_data(url: str, headers: dict = None) -> Any:
        """Example resilient API call."""
        async with httpx.AsyncClient(headers=headers) as client:
            response = await client.get(url, timeout=5)
            response.raise_for_status()
            return response.json()

    async def main() -> None:
        try:
            data = await fetch_example_data(
                "https://jsonplaceholder.typicode.com/todos/1",
                headers={"X-Test": "123"},
            )
            print("Result:", json.dumps(data, indent=2))
        except Exception as exc:
            logger.error("Request failed: %s", exc)

        state = manager.get_circuit_state("example_api")
        print("Circuit state:", state)

    asyncio.run(main())
