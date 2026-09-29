"""`scripts/live_smoke.py` — one live round trip per third-party integration, on staging.

The script spends sandbox money and sends real messages, so what is tested here is what keeps
it safe and honest rather than the gateways themselves (their contracts are pinned by the
respx/Stubber suites):

* it refuses a production environment and any live gateway key or production Dojah host,
  before a single probe runs;
* a probe whose key or test recipient is missing is SKIPPED with the reason, never passed;
* one failing probe fails the run, and a probe's own error is reported against its name;
* the probes drive the same adapters the app uses — shown here against respx and fakes.
"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import respx

from main.app.config.settings import Environment, settings
from main.appodus_utils.config.settings import IntentProvider
from main.appodus_utils.integrations.intent.models import BotIntent, IntentResult

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "live_smoke.py"


def _module():
    spec = importlib.util.spec_from_file_location("live_smoke", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve their annotations through sys.modules, so the module is registered first.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


smoke = _module()


def _env(**overrides):
    base = dict(
        ENVIRONMENT=Environment.STAGING,
        PAYSTACK_SECRET_KEY="sk_test_abc",
        FLUTTERWAVE_SECRET_KEY="FLWSECK_TEST-abc-X",
        DOJAH_BASE_URL="https://sandbox.dojah.io",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestRefusal:
    def test_staging_with_test_keys_and_the_dojah_sandbox_is_allowed(self):
        assert smoke.refusal(_env(), active_env="staging") is None

    def test_unconfigured_keys_are_allowed_their_probes_skip(self):
        assert smoke.refusal(_env(PAYSTACK_SECRET_KEY="CHANGE_ME", FLUTTERWAVE_SECRET_KEY=""), "staging") is None

    @pytest.mark.parametrize("active_env", ["prod", "production", "PROD"])
    def test_a_production_env_file_is_refused(self, active_env):
        assert "production" in smoke.refusal(_env(), active_env=active_env)

    def test_a_production_environment_is_refused(self):
        assert "production" in smoke.refusal(_env(ENVIRONMENT=Environment.PRODUCTION), "staging")

    def test_a_live_paystack_key_is_refused(self):
        assert "PAYSTACK_SECRET_KEY" in smoke.refusal(_env(PAYSTACK_SECRET_KEY="sk_live_abc"), "staging")

    def test_a_live_flutterwave_key_is_refused(self):
        assert "FLUTTERWAVE_SECRET_KEY" in smoke.refusal(_env(FLUTTERWAVE_SECRET_KEY="FLWSECK-abc-X"), "staging")

    def test_dojahs_production_host_is_refused(self):
        assert "DOJAH_BASE_URL" in smoke.refusal(_env(DOJAH_BASE_URL="https://api.dojah.io"), "staging")

    def test_main_refuses_before_any_probe_runs(self, monkeypatch, capsys):
        ran = []
        monkeypatch.setattr(smoke, "PROBES", [smoke.Probe("x", "x", lambda _o: ran.append(1))])
        monkeypatch.setattr(smoke, "settings", _env(ENVIRONMENT=Environment.PRODUCTION))

        assert smoke.main(["--only", "x"]) == 2
        assert ran == []
        assert "Refused" in capsys.readouterr().err


def _probe(name, outcome):
    async def run(_options):
        if outcome == "skip":
            raise smoke.Skip("no key")
        if outcome == "fail":
            raise RuntimeError("gateway said no")
        return "ok"
    return smoke.Probe(name, name, run)


class TestRunner:
    async def test_each_probe_reports_pass_fail_or_skip_under_its_name(self):
        results = await smoke.run_probes(
            [_probe("a", "pass"), _probe("b", "fail"), _probe("c", "skip")], smoke.Options(),
        )

        assert [(r.name, r.outcome) for r in results] == [
            ("a", smoke.Outcome.PASS), ("b", smoke.Outcome.FAIL), ("c", smoke.Outcome.SKIP),
        ]
        assert "gateway said no" in results[1].detail
        assert results[2].detail == "no key"

    def test_only_a_run_where_every_probe_passed_exits_zero(self):
        passed = smoke.Result("a", smoke.Outcome.PASS, "")
        failed = smoke.Result("b", smoke.Outcome.FAIL, "")
        skipped = smoke.Result("c", smoke.Outcome.SKIP, "")

        assert smoke.exit_code([passed]) == 0
        assert smoke.exit_code([passed, failed, skipped]) == smoke.EXIT_FAILED
        # A skipped probe proved nothing: the gate must not go green on it, even alone.
        assert smoke.exit_code([passed, skipped]) == smoke.EXIT_INCOMPLETE
        assert smoke.exit_code([skipped]) == smoke.EXIT_INCOMPLETE

    def test_a_check_holds_under_python_optimise(self):
        """`check`, not `assert`: `python -O` strips asserts, and every probe would pass."""
        with pytest.raises(smoke.CheckFailed, match="empty"):
            smoke.check([], "the bank list is empty")

    def test_only_selects_probes_by_name_in_the_catalogue_order(self):
        names = [p.name for p in smoke.select(["places", "s3"])]
        assert names == [p.name for p in smoke.PROBES if p.name in {"places", "s3"}]

    def test_an_unknown_probe_name_is_an_error(self):
        with pytest.raises(SystemExit):
            smoke.select(["nope"])

    def test_every_register_row_that_can_run_live_has_a_probe(self):
        assert {p.name for p in smoke.PROBES} >= {
            "paystack", "flutterwave", "paystack_transfers", "flutterwave_transfers", "s3",
            "email_resend", "email_mailjet", "email_ses", "sms_termii", "sms_twilio",
            "whatsapp", "intent", "dojah", "places",
        }


class TestProbes:
    async def test_a_probe_without_its_key_skips_and_says_which(self, monkeypatch):
        monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "")

        with pytest.raises(smoke.Skip, match="GOOGLE_PLACES_API_KEY"):
            await smoke.probe_places(smoke.Options())

    async def test_a_probe_without_its_test_recipient_skips(self, monkeypatch):
        monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test")

        with pytest.raises(smoke.Skip, match="--email"):
            await smoke.probe_email_resend(smoke.Options())

    async def test_transfers_reach_the_named_gateway_even_under_payment_stub_mode(self, monkeypatch):
        """`PaymentGatewayFactory.transfers()` hands out the stub under PAYMENT_STUB_MODE, which
        would let the probe pass without the gateway ever being called."""
        from main.appodus_utils.integrations.payment.gateway.models import GatewayAccount, GatewayBank
        from main.appodus_utils.integrations.payment.gateway.stub import StubTransferGateway

        class Flutterwave(StubTransferGateway):
            async def resolve_account(self, bank_code, account_number):
                return GatewayAccount(bank_code=bank_code, account_number=account_number, account_name="TEST")

            async def list_banks(self, currency):
                return [GatewayBank(code="044", name="Access")]

        class Factory:
            def for_platform(self, platform):
                return Flutterwave()

            def transfers(self, platform):
                raise AssertionError("the probe must not take the stub-aware path")

        monkeypatch.setattr(settings, "PAYMENT_STUB_MODE", True)
        monkeypatch.setattr(settings, "FLUTTERWAVE_SECRET_KEY", "FLWSECK_TEST-x")
        monkeypatch.setattr(smoke, "_payment_gateways", lambda: Factory())

        detail = await smoke.probe_flutterwave_transfers(smoke.Options())

        assert "resolved 'TEST'" in detail

    async def test_dojah_needs_a_real_selfie(self, monkeypatch):
        monkeypatch.setattr(settings, "DOJAH_APP_ID", "app")
        monkeypatch.setattr(settings, "DOJAH_PRIVATE_KEY", "test_sk")

        with pytest.raises(smoke.Skip, match="--selfie"):
            await smoke.probe_dojah(smoke.Options())

    @respx.mock
    async def test_places_suggests_then_resolves_a_place_in_one_session(self, monkeypatch):
        base = "https://places.googleapis.test/v1"
        monkeypatch.setattr(settings, "GOOGLE_PLACES_BASE_URL", base)
        monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "AIza-test")
        suggest = respx.post(f"{base}/places:autocomplete").mock(return_value=httpx.Response(200, json={
            "suggestions": [{"placePrediction": {"placeId": "ChIJ-l", "text": {"text": "Lekki, Lagos"}}}],
        }))
        details = respx.get(f"{base}/places/ChIJ-l").mock(return_value=httpx.Response(200, json={
            "id": "ChIJ-l", "formattedAddress": "Lekki, Lagos, Nigeria",
            "location": {"latitude": 6.44, "longitude": 3.47}, "addressComponents": [],
        }))

        detail = await smoke.probe_places(smoke.Options())

        assert "Lekki, Lagos, Nigeria" in detail
        session = suggest.calls.last.request.content
        assert details.calls.last.request.url.params["sessionToken"].encode() in session

    async def test_intent_fails_on_any_misread_utterance(self, monkeypatch):
        misread = BotIntent.MENU

        class Classifier:
            platform = IntentProvider.OPENAI_COMPATIBLE

            async def classify(self, text):
                expected = dict(smoke.INTENT_CASES)[text]
                return IntentResult(intent=misread if expected == BotIntent.PRICING else expected)

        monkeypatch.setattr(settings, "INTENT_API_KEY", "sk-test")
        monkeypatch.setattr(smoke, "_active_classifier", lambda: Classifier())

        with pytest.raises(smoke.CheckFailed, match="PRICING"):
            await smoke.probe_intent(smoke.Options())

    async def test_intent_on_the_stub_is_skipped_not_passed(self, monkeypatch):
        class Stub:
            platform = IntentProvider.STUB

        monkeypatch.setattr(settings, "INTENT_API_KEY", "sk-test")
        monkeypatch.setattr(smoke, "_active_classifier", lambda: Stub())

        with pytest.raises(smoke.Skip, match="INTENT_PROVIDER"):
            await smoke.probe_intent(smoke.Options())
