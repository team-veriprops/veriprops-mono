from unittest.mock import MagicMock
from circuitbreaker import CircuitBreaker


class TestResilienceManager:
    def __init__(self):
        self.messaging_circuit_breaker = MagicMock(spec=CircuitBreaker)
        self.messaging_circuit_breaker.side_effect = lambda *args, **kwargs: lambda f: f

        self.messaging_retry = MagicMock()
        self.messaging_retry.side_effect = lambda *args, **kwargs: lambda f: f


test_resilience_manager = TestResilienceManager()
