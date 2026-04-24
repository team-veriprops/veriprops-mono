from typing import Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    start_http_server
)


class MetricsManager:
    def __init__(self, port: int = 8001):
        self.port = port
        self._init_metrics()

    def _init_metrics(self):
        # Message metrics
        self.messages_sent = Counter(
            'messages_sent_total',
            'Total messages sent',
            ['channel', 'provider', 'status']
        )

        self.message_latency = Histogram(
            'message_latency_seconds',
            'Message delivery latency',
            ['channel', 'provider'],
            buckets=[0.1, 0.5, 1, 2, 5, 10]
        )

        # Provider metrics
        self.provider_errors = Counter(
            'provider_errors_total',
            'Total provider errors',
            ['provider', 'error_type']
        )

        self.circuit_breaker_state = Gauge(
            'circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=open)',
            ['provider']
        )

        # Cost metrics
        self.message_cost = Gauge(
            'message_cost_usd',
            'Cost per message in USD',
            ['channel', 'provider']
        )

        # Queue metrics
        self.queue_size = Gauge(
            'message_queue_size',
            'Number of messages in queue',
            ['channel', 'priority']
        )

    def start_metrics_server(self):
        start_http_server(self.port)

    def track_message(self, channel: str, provider: str, status: str, duration: Optional[float] = None):
        self.messages_sent.labels(channel, provider, status).inc()
        if duration is not None:
            self.message_latency.labels(channel, provider).observe(duration)

    def track_error(self, provider: str, error_type: str):
        self.provider_errors.labels(provider, error_type).inc()

    def update_circuit_state(self, provider: str, is_open: bool):
        self.circuit_breaker_state.labels(provider).set(1 if is_open else 0)

    def track_cost(self, channel: str, provider: str, cost: float):
        self.message_cost.labels(channel, provider).set(cost)

    def update_queue_size(self, channel: str, priority: str, size: int):
        self.queue_size.labels(channel, priority).set(size)


# Initialize metrics
metrics_manager = MetricsManager()
