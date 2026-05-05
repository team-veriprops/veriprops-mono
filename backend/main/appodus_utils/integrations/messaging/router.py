from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from circuitbreaker import CircuitBreakerError
from kink import inject, di

from main.appodus_utils.config.bootstrap import base_di_bootstrap
from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.config.settings import Environment
from main.appodus_utils.integrations.exception.exceptions import IntegrationFatalException
from main.appodus_utils.integrations.messaging.models import Stat, MessageProviderName
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.integrations.messaging.services.cost_tracking import cost_tracker, CostRecord
from main.appodus_utils.integrations.messaging.services.resilience import resilience_manager

logger: Logger = di['logger']

# Sentinel used in sort key to make None last_used sort consistently.
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class ProviderRoute:
    def __init__(self, provider: IMessageProvider, sender: Callable):
        self._provider = provider
        self.sender = sender  # always set at construction — never None
        self.stats: Stat = Stat(
            success=0,
            failure=0,
            last_used=None,
            cost_per_unit=Decimal(0.0)
        )

    @property
    def success_rate(self) -> float:
        total = self.stats.success + self.stats.failure
        return self.stats.success / total if total > 0 else 1.0

    @property
    def provider(self) -> IMessageProvider:
        return self._provider


base_di_bootstrap.register_all_subclasses(IMessageProvider)


@inject
class MessageRouter:
    def __init__(self, providers: List[IMessageProvider] = di[List[IMessageProvider]]):
        # Keyed by channel for channel-scoped routing.
        self.providers: Dict[str, List[ProviderRoute]] = {}
        # Flat index for O(1) lookup by provider name across all channels.
        self._route_index: Dict[str, ProviderRoute] = {}
        self._initialize_providers(providers)
        self.routing_rules = self._load_routing_rules()

    def _initialize_providers(self, providers: List[IMessageProvider]) -> None:
        # Kink injects instances, not classes — List[IMessageProvider] is correct.
        for provider in providers:
            # Build sender first, pass it into ProviderRoute at construction.
            # This ensures the attribute is always fully initialised — no
            # late assignment, no type checker warnings.
            sender = self._build_sender(provider)
            route = ProviderRoute(provider, sender)
            self._route_index[provider.name] = route
            for channel in provider.supported_channels:
                if channel not in self.providers:
                    self.providers[channel] = []
                self.providers[channel].append(route)

    def _build_sender(self, provider: IMessageProvider) -> Callable:
        """Build a resilient send closure for *provider* with its own circuit.

        Called once per provider at initialisation time, not per message.
        Each provider gets an independent circuit breaker keyed by provider.name
        so that Termii failures do not open the circuit for Twilio.
        """
        @resilience_manager.messaging_retry()
        @resilience_manager.messaging_circuit_breaker(name=provider.name)
        async def _send(message: UpsertMessageDto) -> UpsertMessageDto:
            result = await provider.send_message(message)  # raises on failure
            self._update_stats(provider, success=True)
            await self._track_cost(provider, result)
            return result

        return _send

    def _get_route(self, provider_name: MessageProviderName) -> Optional[ProviderRoute]:
        """O(1) route lookup by provider name."""
        return self._route_index.get(provider_name)

    def _get_provider_by_name(
        self, provider_name: MessageProviderName
    ) -> Optional[IMessageProvider]:
        route = self._get_route(provider_name)
        return route.provider if route else None

    @staticmethod
    def _load_routing_rules() -> Dict:
        """Load routing rules from config/database."""
        return {
            "sms": {
                "rules": [
                    {
                        # Test/dev/local: suppress all SMS. Single-path, no fallback.
                        # Exclusive=True prevents last-resort fallback to real SMS providers.
                        "condition": lambda msg: settings.ENVIRONMENT in {
                            Environment.TEST, Environment.DEVELOPMENT, Environment.LOCAL
                        },
                        "providers": [MessageProviderName.MOCK_SMS],
                        "fallback_order": [],
                        "exclusive": True,
                    },
                    {
                        "condition": lambda msg: msg.recipient.startswith("+234"),
                        "providers": [MessageProviderName.TERMII_SMS, MessageProviderName.TWILIO_SMS],
                        "fallback_order": [MessageProviderName.TERMII_SMS, MessageProviderName.TWILIO_SMS],
                    },
                    {
                        "condition": lambda msg: msg.priority == "high",
                        "providers": [MessageProviderName.TWILIO_SMS],
                        "fallback_order": [MessageProviderName.TWILIO_SMS, MessageProviderName.TERMII_SMS],
                    },
                ],
                "default": [MessageProviderName.TWILIO_SMS, MessageProviderName.TERMII_SMS],
            },
            "email": {
                "rules": [
                    {
                        # Route to local Mailpit SMTP in dev/test/local envs.
                        # Production and staging always use external providers.
                        # Exclusive=True prevents last-resort fallback to Mailjet/Sendgrid
                        # if SMTP fails — misconfigurations fail loudly, not silently.
                        "condition": lambda msg: settings.ENVIRONMENT not in {
                            Environment.PRODUCTION, Environment.STAGING
                        },
                        "providers": [MessageProviderName.SMTP],
                        "fallback_order": [],
                        "exclusive": True,
                    }
                ],
                "default": [MessageProviderName.MAILJET, MessageProviderName.SENDGRID_EMAIL],
            },
        }

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        """Send a message with full resilience and graceful degradation.

        Selects a provider, runs through retry + circuit breaking, then
        falls back only after all retries are exhausted or the circuit is open.
        """
        provider = self._select_provider(message)
        route = self._get_route(provider.name)

        if route is None:
            raise ValueError(
                f"Provider '{provider.name}' was selected but has no registered route. "
                "This indicates a misconfiguration in provider registration."
            )

        try:
            return await route.sender(message)

        except CircuitBreakerError as e:
            logger.error(
                "Circuit open for provider %s, using fallback: %s",
                provider.name, e
            )
            self._update_stats(provider, success=False)
            return await self._handle_fallback(message, provider)

        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(
                "All retries exhausted for provider %s, using fallback: %s",
                provider.name, e
            )
            self._update_stats(provider, success=False)
            return await self._handle_fallback(message, provider)

    async def get_message_status(
        self, provider: MessageProviderName, provider_id: str
    ) -> Optional[Any]:
        message_provider = self._get_provider_by_name(provider)
        if message_provider:
            return await message_provider.get_message_status(provider_id)
        return None

    def _select_provider(self, message: UpsertMessageDto) -> IMessageProvider:
        """Select a provider based on routing rules and success rate."""
        channel = message.channel
        available_routes = self.providers.get(channel, [])

        if not available_routes:
            raise ValueError(f"No providers available for channel: {channel}")

        if channel in self.routing_rules:
            for rule in self.routing_rules[channel]["rules"]:
                if rule["condition"](message):
                    for provider_name in rule["providers"]:
                        route = self._get_route(provider_name)
                        if route and route in available_routes:
                            return route.provider

        # Default: sort by descending success rate, then by last_used ascending.
        # last_used is None on cold start — substitute _EPOCH so None values
        # sort consistently rather than raising TypeError on comparison.
        return sorted(
            available_routes,
            key=lambda r: (-r.success_rate, r.stats.last_used or _EPOCH)
        )[0].provider

    async def _handle_fallback(
        self,
        message: UpsertMessageDto,
        failed_provider: IMessageProvider,
    ) -> UpsertMessageDto:
        """Try remaining providers in fallback order using their cached senders.

        Each fallback attempt goes through the provider's cached resilient sender,
        so retries and per-provider circuit breakers apply to fallbacks too.
        """
        channel = message.channel
        attempted: List[str] = [failed_provider.name]

        async def _try_route(route: ProviderRoute) -> Optional[UpsertMessageDto]:
            """Attempt delivery via *route*; return result or None on failure."""
            try:
                return await route.sender(message)
            except Exception as e:
                logger.warning(
                    "Fallback provider %s failed: %s", route.provider.name, e
                )
                self._update_stats(route.provider, success=False)
                return None

        # Follow the fallback order from routing rules.
        if channel in self.routing_rules:
            for rule in self.routing_rules[channel]["rules"]:
                if failed_provider.name in rule["providers"]:
                    for fallback_name in rule["fallback_order"]:
                        if fallback_name in attempted:
                            continue
                        route = self._get_route(fallback_name)
                        if not route:
                            continue
                        attempted.append(fallback_name)
                        result = await _try_route(route)
                        if result is not None:
                            return result

        # If the matched rule is exclusive, do not fall through to last-resort providers.
        # Exclusive rules are environment-gated (e.g. SMTP in dev/test, MOCK_SMS in test).
        # A failure in those environments should propagate immediately, not silently
        # retry via production providers.
        if channel in self.routing_rules:
            for rule in self.routing_rules[channel]["rules"]:
                if failed_provider.name in rule.get("providers", []) and rule.get("exclusive"):
                    raise IntegrationFatalException(
                        f"Provider '{failed_provider.name}' failed and its routing rule is "
                        f"exclusive — no last-resort fallback allowed for channel '{channel}'. "
                        f"Attempted: {attempted}"
                    )

        # Last resort: any remaining provider not yet attempted.
        for route in self.providers.get(channel, []):
            if route.provider.name in attempted:
                continue
            attempted.append(route.provider.name)
            result = await _try_route(route)
            if result is not None:
                return result

        raise IntegrationFatalException(
            f"All providers failed for channel '{channel}'. Attempted: {attempted}"
        )

    def _update_stats(self, provider: IMessageProvider, *, success: bool) -> None:
        route = self._get_route(provider.name)
        if route is None:
            return
        if success:
            route.stats.success += 1
        else:
            route.stats.failure += 1
        route.stats.last_used = datetime.now(timezone.utc)

    async def _track_cost(
        self, provider: IMessageProvider, message: UpsertMessageDto
    ) -> None:
        cost = await provider.get_cost(message.id)
        cost_tracker.record_cost(CostRecord(
            provider=provider.name,
            channel=message.channel,
            cost=cost,
            message_id=message.id,
            timestamp=datetime.now(timezone.utc)
        ))
