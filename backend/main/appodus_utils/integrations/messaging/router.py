import asyncio
import json

from circuitbreaker import CircuitBreakerError
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from kink import inject, di
from logging import Logger
from typing import Any, Callable, Dict, List, Optional, Tuple

from main.app.config.settings import settings
from main.app.domain.message.models import UpsertMessageDto
from main.appodus_utils.config.bootstrap import base_di_bootstrap
from main.appodus_utils.config.settings import Environment, WhatsAppProvider
from main.appodus_utils.db.redis_utils import RedisUtils
from main.appodus_utils.integrations.exception.exceptions import IntegrationFatalException
from main.appodus_utils.integrations.messaging.models import Stat, MessagePriority, MessageProviderName
from main.appodus_utils.integrations.messaging.providers.models import IMessageProvider
from main.appodus_utils.integrations.messaging.qa_recipients import is_qa_recipient
from main.appodus_utils.integrations.messaging.services.cost_tracking import cost_tracker, CostRecord
from main.appodus_utils.integrations.messaging.services.resilience import resilience_manager

logger: Logger = di['logger']

# Sentinel used in sort key to make None last_used sort consistently.
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)
_STATS_KEY_PREFIX = "messaging_stats"
_STATS_TTL = timedelta(hours=24)


def _staging_fixture(message: UpsertMessageDto) -> bool:
    """A message on staging addressed only to QA fixtures (`qa_recipients.py`)."""
    if settings.ENVIRONMENT != Environment.STAGING:
        return False
    recipients = message.to.recipient if isinstance(message.to.recipient, list) else [message.to.recipient]
    return all(is_qa_recipient(message.channel, r) for r in recipients)


def _single_recipient(message: UpsertMessageDto) -> str:
    """The one recipient of an SMS or WhatsApp message, which validation allows as a
    one-element list."""
    recipient = message.to.recipient
    return recipient[0] if isinstance(recipient, list) else recipient


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
    def __init__(self, providers: List[IMessageProvider]):
        # Keyed by channel for channel-scoped routing.
        self.providers: Dict[str, List[ProviderRoute]] = {}
        # Flat index for O(1) lookup by provider name across all channels.
        self._route_index: Dict[Tuple[str, str], ProviderRoute] = {}
        self._provider_index: Dict[str, IMessageProvider] = {}
        self._initialize_providers(providers)
        self.routing_rules = self._load_routing_rules()
        # Schedule Redis stats load — fires after the current event loop tick.
        try:
            asyncio.get_running_loop().create_task(self._load_stats())
        except RuntimeError:
            pass  # No running loop at import time — stats start at zero.

    def _initialize_providers(self, providers: List[IMessageProvider]) -> None:
        seen: set = set()
        for provider in providers:
            if provider.name in seen:
                logger.warning(
                    "Duplicate provider '{}' — skipping second registration", provider.name
                )
                continue
            seen.add(provider.name)
            self._provider_index[provider.name] = provider
            for channel in provider.supported_channels:
                sender = self._build_sender(provider, channel)
                route = ProviderRoute(provider, sender)
                self._route_index[(provider.name, channel)] = route
                self.providers.setdefault(channel, []).append(route)

    def _build_sender(self, provider: IMessageProvider, channel: str) -> Callable:
        """Build a resilient send closure for *provider*/*channel* with its own circuit.

        Called once per (provider, channel) at initialisation. Each provider gets
        an independent circuit breaker keyed by provider.name so that Termii
        failures do not open the circuit for Twilio.
        """
        @resilience_manager.messaging_retry()
        @resilience_manager.messaging_circuit_breaker(name=provider.name)
        async def _send(message: UpsertMessageDto) -> UpsertMessageDto:
            result = await provider.send_message(message)  # raises on failure
            self._update_stats(provider.name, channel, success=True)
            try:
                await self._track_cost(provider, result)
            except Exception as e:
                logger.warning(
                    "Cost tracking failed for provider {}: {}", provider.name, e
                )
            return result

        return _send

    def _get_route(self, provider_name: str, channel: str) -> Optional[ProviderRoute]:
        """O(1) route lookup by (provider_name, channel)."""
        return self._route_index.get((provider_name, channel))

    def _get_provider_by_name(
        self, provider_name: MessageProviderName
    ) -> Optional[IMessageProvider]:
        return self._provider_index.get(provider_name)

    @staticmethod
    def _load_routing_rules() -> Dict:
        """Load routing rules from config/database."""
        return {
            "sms": {
                "rules": [
                    {
                        # Staging sends for real, and /dev/seed and /dev/scenario run there: a
                        # QA fixture's address is recorded by the sink, never sent to its owner.
                        "condition": _staging_fixture,
                        "providers": [MessageProviderName.QA_SINK],
                        "fallback_order": [],
                        "exclusive": True,
                    },
                    {
                        # Test/dev/dev_personal: suppress all SMS. Single-path, no fallback.
                        # Exclusive=True prevents last-resort fallback to real SMS providers.
                        "condition": lambda msg: settings.ENVIRONMENT in {
                            Environment.TEST, Environment.DEVELOPMENT, Environment.DEV_PERSONAL
                        },
                        "providers": [MessageProviderName.MOCK_SMS],
                        "fallback_order": [],
                        "exclusive": True,
                    },
                    {
                        "condition": lambda msg: _single_recipient(msg).startswith("+234"),
                        "providers": [MessageProviderName.TERMII_SMS, MessageProviderName.TWILIO_SMS],
                        "fallback_order": [MessageProviderName.TERMII_SMS, MessageProviderName.TWILIO_SMS],
                    },
                    {
                        "condition": lambda msg: msg.priority == MessagePriority.HIGH,
                        "providers": [MessageProviderName.TWILIO_SMS],
                        "fallback_order": [MessageProviderName.TWILIO_SMS, MessageProviderName.TERMII_SMS],
                    },
                ],
                "default": [MessageProviderName.TWILIO_SMS, MessageProviderName.TERMII_SMS],
            },
            "email": {
                "rules": [
                    {
                        # Staging sends for real, and /dev/seed and /dev/scenario run there: a
                        # QA fixture's address is recorded by the sink, never sent to its owner.
                        "condition": _staging_fixture,
                        "providers": [MessageProviderName.QA_SINK],
                        "fallback_order": [],
                        "exclusive": True,
                    },
                    {
                        # Route to local Mailpit SMTP in dev/test/dev_personal envs.
                        # Production and staging always use external providers.
                        # Exclusive=True prevents last-resort fallback to Mailjet
                        # if SMTP fails — misconfigurations fail loudly, not silently.
                        "condition": lambda msg: settings.ENVIRONMENT not in {
                            Environment.PRODUCTION, Environment.STAGING
                        },
                        "providers": [MessageProviderName.SMTP],
                        "fallback_order": [],
                        "exclusive": True,
                    },
                    {
                        # Production and staging: Resend primary, Mailjet then AWS SES
                        # as automatic fallbacks.
                        "condition": lambda msg: settings.ENVIRONMENT in {
                            Environment.PRODUCTION, Environment.STAGING
                        },
                        "providers": [
                            MessageProviderName.RESEND,
                            MessageProviderName.MAILJET,
                            MessageProviderName.AWS_SES,
                        ],
                        "fallback_order": [
                            MessageProviderName.RESEND,
                            MessageProviderName.MAILJET,
                            MessageProviderName.AWS_SES,
                        ],
                    },
                ],
                "default": [
                    MessageProviderName.RESEND,
                    MessageProviderName.MAILJET,
                    MessageProviderName.AWS_SES,
                ],
            },
            "whatsapp": {
                "rules": [
                    {
                        # The transport is an explicit contract, not a fallback chain
                        # (PRD §26, D43): CI and e2e run entirely on the stub, and both
                        # rules are exclusive so a misconfiguration can never silently
                        # cross over — production reaching the stub, or a test run
                        # reaching Meta, are both startup failures instead.
                        "condition": lambda msg: settings.WHATSAPP_PROVIDER == WhatsAppProvider.STUB,
                        "providers": [MessageProviderName.WHATSAPP_STUB],
                        "fallback_order": [],
                        "exclusive": True,
                    },
                    {
                        "condition": lambda msg: settings.WHATSAPP_PROVIDER == WhatsAppProvider.META,
                        "providers": [MessageProviderName.WHATSAPP_BUSINESS],
                        "fallback_order": [],
                        "exclusive": True,
                    },
                ],
                # Empty on purpose: the two exclusive rules above cover every setting,
                # and the stub must never be a default for a live send.
                "default": [],
            },
        }

    async def send_message(self, message: UpsertMessageDto) -> UpsertMessageDto:
        """Send a message with full resilience and graceful degradation.

        Selects a provider, runs through retry + circuit breaking, then
        falls back only after all retries are exhausted or the circuit is open.
        """
        provider = self._select_provider(message)
        route = self._get_route(provider.name, message.channel)

        if route is None:
            raise ValueError(
                f"Provider '{provider.name}' was selected but has no registered route. "
                "This indicates a misconfiguration in provider registration."
            )

        try:
            return await route.sender(message)

        except CircuitBreakerError as e:
            # A warning: the fallback may still deliver (see the retries-exhausted case below).
            logger.warning(
                "Circuit open for provider {}, using fallback: {}",
                provider.name, e
            )
            self._update_stats(provider.name, message.channel, success=False)
            return await self._handle_fallback(message, provider)

        except Exception as e:
            # Re-raise fatal exceptions immediately — they indicate a configuration
            # error or an unrecoverable state that fallback cannot fix.
            if isinstance(e, IntegrationFatalException):
                raise
            # A warning, not an error: the fallback may still deliver, and if it cannot, the
            # failure it raises is logged once as the fault it is (`log_fault_once`).
            logger.warning(
                "All retries exhausted for provider {}, using fallback: {}",
                provider.name, e
            )
            self._update_stats(provider.name, message.channel, success=False)
            return await self._handle_fallback(message, provider)

    async def get_message_status(
        self, provider: MessageProviderName, provider_id: str
    ) -> Optional[Any]:
        message_provider = self._get_provider_by_name(provider)
        if message_provider:
            return await message_provider.get_message_status(provider_id)
        return None

    def _select_provider(self, message: UpsertMessageDto) -> IMessageProvider:
        """Select the best available provider for *message*.

        Rule-matched providers whose circuit is open are skipped in favour of
        the next candidate in the rule's providers list. The default sort
        deprioritises open-circuit providers by placing them last.
        """
        channel = message.channel
        available_routes = self.providers.get(channel, [])

        if not available_routes:
            raise ValueError(f"No providers available for channel: {channel}")

        if channel in self.routing_rules:
            for rule in self.routing_rules[channel]["rules"]:
                if rule["condition"](message):
                    candidates = [
                        route for route in (self._get_route(name, channel) for name in rule["providers"])
                        if route and route in available_routes
                    ]
                    for route in candidates:
                        if not resilience_manager.get_circuit_state(route.provider.name).get("open", False):
                            return route.provider
                    # An exclusive rule owns the message even while its circuit is open: the
                    # send fails on that provider, and never falls through to another rule or
                    # the default list (a test run reaching Termii, or a live WhatsApp send
                    # being recorded by the stub).
                    if rule.get("exclusive") and candidates:
                        return candidates[0].provider

        # Default: open-circuit providers last, then descending success rate, then LRU.
        # last_used is None on cold start — substitute _EPOCH so None values
        # sort consistently rather than raising TypeError on comparison.
        default_routes = self._default_routes(channel)
        if not default_routes:
            raise ValueError(f"No default providers available for channel: {channel}")
        return sorted(
            default_routes,
            key=lambda r: (
                resilience_manager.get_circuit_state(r.provider.name).get("open", False),
                -r.success_rate,
                r.stats.last_used or _EPOCH,
            )
        )[0].provider

    def _default_routes(self, channel: str) -> List[ProviderRoute]:
        """Routes a message may use when no rule claims it, in the channel's declared order.

        Every provider is registered in every environment, including the mock and local ones
        (MOCK_SMS, SMTP). Only a rule may route to those, so an unmatched message or a
        last-resort fallback can never be "delivered" by a provider that sends nothing.
        A channel without a declared default keeps every registered route.
        """
        registered = self.providers.get(channel, [])
        rules = self.routing_rules.get(channel)
        if not rules or "default" not in rules:
            return list(registered)
        by_name = {route.provider.name: route for route in registered}
        return [by_name[name] for name in rules["default"] if name in by_name]

    async def _handle_fallback(
        self,
        message: UpsertMessageDto,
        failed_provider: IMessageProvider,
    ) -> UpsertMessageDto:
        """Try remaining providers in fallback order using their cached senders.

        Each fallback attempt goes through the provider's cached resilient sender,
        so retries and per-provider circuit breakers apply to fallbacks too.

        A single rule scan covers both fallback_order traversal and the exclusive
        guard, avoiding a second O(n_rules) pass.
        """
        channel = message.channel
        attempted: List[str] = [failed_provider.name]
        matched_rule = None

        async def _try_route(route: ProviderRoute) -> Optional[UpsertMessageDto]:
            """Attempt delivery via *route*; return result or None on failure."""
            try:
                return await route.sender(message)
            except Exception as e:
                logger.warning(
                    "Fallback provider {} failed: {}", route.provider.name, e
                )
                self._update_stats(route.provider.name, channel, success=False)
                return None

        # Single pass: find the first rule that owns the failed provider, follow
        # its fallback_order, and record whether the rule is exclusive.
        if channel in self.routing_rules:
            for rule in self.routing_rules[channel]["rules"]:
                if failed_provider.name in rule["providers"]:
                    matched_rule = rule
                    for fallback_name in rule["fallback_order"]:
                        if fallback_name in attempted:
                            continue
                        route = self._get_route(fallback_name, channel)
                        if not route:
                            continue
                        attempted.append(fallback_name)
                        result = await _try_route(route)
                        if result is not None:
                            return result
                    break  # stop at the first matching rule

        # If the matched rule is exclusive, do not fall through to last-resort providers.
        # Exclusive rules are environment-gated (e.g. SMTP in dev/test, MOCK_SMS in test).
        # A failure in those environments should propagate immediately, not silently
        # retry via production providers.
        if matched_rule and matched_rule.get("exclusive"):
            raise IntegrationFatalException(
                f"Provider '{failed_provider.name}' failed and its routing rule is "
                f"exclusive — no last-resort fallback allowed for channel '{channel}'. "
                f"Attempted: {attempted}"
            )

        # Last resort: any remaining default provider not yet attempted.
        for route in self._default_routes(channel):
            if route.provider.name in attempted:
                continue
            attempted.append(route.provider.name)
            result = await _try_route(route)
            if result is not None:
                return result

        raise IntegrationFatalException(
            f"All providers failed for channel '{channel}'. Attempted: {attempted}"
        )

    def _update_stats(self, provider_name: str, channel: str, *, success: bool) -> None:
        route = self._get_route(provider_name, channel)
        if route is None:
            return
        if success:
            route.stats.success += 1
        else:
            route.stats.failure += 1
        route.stats.last_used = datetime.now(timezone.utc)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist_stats(provider_name, channel, route.stats))
        except RuntimeError:
            # No running event loop — stat is updated in-memory only.
            pass

    async def _persist_stats(self, provider_name: str, channel: str, stats: Stat) -> None:
        """Write provider stats to Redis with a 24-hour TTL (best-effort)."""
        key = f"{_STATS_KEY_PREFIX}:{provider_name}:{channel}"
        payload = json.dumps({
            "success": stats.success,
            "failure": stats.failure,
            "last_used": stats.last_used.isoformat() if stats.last_used else None,
        })
        await RedisUtils.set_redis(key, payload, _STATS_TTL)

    async def _load_stats(self) -> None:
        """Restore provider stats from Redis on first send_message call."""
        for (provider_name, channel), route in self._route_index.items():
            key = f"{_STATS_KEY_PREFIX}:{provider_name}:{channel}"
            raw = await RedisUtils.get_redis(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                route.stats.success = data.get("success", 0)
                route.stats.failure = data.get("failure", 0)
                last_used = data.get("last_used")
                if last_used:
                    route.stats.last_used = datetime.fromisoformat(last_used)
            except Exception as e:
                logger.warning(
                    "Failed to restore stats for {}/{}: {}", provider_name, channel, e
                )

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
