"""Live sandbox smoke: one real round trip per third-party integration, on staging credentials.

CI and e2e never leave the stubs, and the respx/Stubber contract tests pin each adapter to the
provider's *documented* shapes. This is the other half: the same adapters the app uses, called
for real with the staging sandbox keys, so a wrong field name, an unsigned header or a
misread answer shows up here rather than in front of a customer. It is the release gate the
third-party register in docs/progress.md points at (runbook: docs/live-integration-smoke.md).

Every probe prints PASS, FAIL or SKIP. SKIP means a key or a test recipient is missing. The exit
code is 0 only when every probe selected passed: any FAIL exits 1, and a run that skipped any
probe exits 3 (incomplete), so a gate can never go green on probes that did not run.

Safety: it refuses to start under a production environment, with a live gateway key, or on
Dojah's production host, before any probe runs. It never touches the database. What it does
spend is sandbox money and real messages to the recipients you pass it.

What it does not cover, and where that lives instead:
* paying on a gateway's hosted page, the webhook, PAID and the refund — the `@live` Playwright
  spec, which drives a real browser through staging (`frontend/e2e/specs/live-integrations.spec.ts`);
* the report PDF and the reviewer's KYC photos on the deployed runtime — the same spec.

Run from backend/ (the whole catalogue, or a few probes by name):
    doppler run --config stg -- python scripts/live_smoke.py \
        --email you@example.com --phone +2348030000000 --whatsapp 2348030000000 --selfie me.jpg
    doppler run --config stg -- python scripts/live_smoke.py --only places,dojah --selfie me.jpg
    python scripts/live_smoke.py --list
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import enum
import io
import os
import secrets
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Sequence
from urllib.parse import urlparse

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import httpx  # noqa: E402
from kink import di  # noqa: E402
from pydantic import SecretStr  # noqa: E402

from main.app.config.bootstrap import di_bootstrap  # noqa: E402,F401  (registers the adapters)
from main.app.config.settings import DOJAH_SANDBOX_HOST, Environment, IntegratedPlatform, settings  # noqa: E402
from main.appodus_utils.config.settings import IntentProvider, is_configured_secret  # noqa: E402
from main.appodus_utils.db.types.money import TransactionCurrency  # noqa: E402
from main.appodus_utils.integrations.exception.exceptions import IntegrationException  # noqa: E402

# ─── Outcomes ───────────────────────────────────────────────────────────────────────


class Outcome(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


class Skip(Exception):
    """The probe could not run: a key or a test recipient is missing. The message says which."""


class CheckFailed(Exception):
    """A probe's expectation did not hold."""


def check(condition: object, message: str) -> None:
    """A probe's verdict. Not ``assert``: ``python -O`` strips those, and every probe would pass."""
    if not condition:
        raise CheckFailed(message)


@dataclass(frozen=True)
class Result:
    name: str
    outcome: Outcome
    detail: str


@dataclass(frozen=True)
class Options:
    """The test assets a run is given. Each is optional; the probes needing one skip without it."""

    email: Optional[str] = None           # an inbox you can read
    phone: Optional[str] = None           # a Nigerian handset, E.164 (+234…), for Termii
    intl_phone: Optional[str] = None      # a non-Nigerian handset, E.164, for Twilio
    whatsapp: Optional[str] = None        # digits only; on Meta's test number it must be allow-listed
    selfie: Optional[Path] = None         # a JPEG of a real, live face
    paystack_bank: Optional[str] = None   # "bank_code:account_number" of a Paystack test account
    send_transfer: bool = False           # actually send ₦100 per transfer gateway


@dataclass(frozen=True)
class Probe:
    name: str
    summary: str
    run: Callable[[Options], Awaitable[str]]


# ─── Safety ─────────────────────────────────────────────────────────────────────────

# APPODUS_ACTIVE_ENV names the env file (`.env.prod`); "production" is refused too, as a typo.
_PRODUCTION_ENV_FILES = {Environment.PRODUCTION.value, "production"}


def refusal(env, active_env: Optional[str]) -> Optional[str]:
    """Why this run must not start, or ``None``. Checked before any probe runs.

    Production is refused outright, and so is anything that would move real money or pay for
    a real identity check: a live gateway key or Dojah's production host. An unset key is fine
    — its probes skip.
    """
    if (active_env or "").lower() in _PRODUCTION_ENV_FILES or env.ENVIRONMENT == Environment.PRODUCTION:
        return "this is a production environment; the smoke runs on staging's sandbox keys only"
    paystack = env.PAYSTACK_SECRET_KEY or ""
    if is_configured_secret(paystack) and not paystack.startswith("sk_test_"):
        return "PAYSTACK_SECRET_KEY is not a test key (sk_test_…)"
    flutterwave = env.FLUTTERWAVE_SECRET_KEY or ""
    if is_configured_secret(flutterwave) and "_TEST" not in flutterwave:
        return "FLUTTERWAVE_SECRET_KEY is not a test key (FLWSECK_TEST-…)"
    if DOJAH_SANDBOX_HOST not in (env.DOJAH_BASE_URL or ""):
        return f"DOJAH_BASE_URL is not Dojah's sandbox ({DOJAH_SANDBOX_HOST})"
    return None


def _require(*keys: str) -> None:
    missing = [key for key in keys if not is_configured_secret(getattr(settings, key, None))]
    if missing:
        raise Skip(f"{', '.join(missing)} not set")


def _recipient(value: Optional[str], flag: str) -> str:
    if not value:
        raise Skip(f"no test recipient (pass {flag})")
    return value


def _smoke_reference(prefix: str) -> str:
    """A fresh reference both gateways accept (lowercase, 16+ characters), marked as a smoke."""
    return f"smoke_{prefix}_{secrets.token_hex(8)}"


# ─── Payments: collection ───────────────────────────────────────────────────────────

_CHARGE_MINOR = 10_000  # ₦100


def _payment_gateways():
    from main.appodus_utils.integrations.factory import PaymentGatewayFactory
    return di[PaymentGatewayFactory]


async def _collection(platform: IntegratedPlatform, key: str) -> str:
    """Open a hosted checkout, then read the unpaid charge back by our reference.

    Paying it needs a browser on the gateway's page — the `@live` spec does that."""
    from main.appodus_utils.integrations.payment.gateway.models import GatewayChargeStatus, HostedCheckoutRequest

    _require(key)
    gateway = _payment_gateways().for_platform(platform)
    reference = _smoke_reference(platform.value[:3])
    url = await gateway.create_hosted_checkout(HostedCheckoutRequest(
        reference=reference, amount_minor=_CHARGE_MINOR, currency=TransactionCurrency.NGN,
        redirect_url=f"{settings.BACKEND_PUBLIC_ORIGIN.rstrip('/')}/smoke-return",
        customer_email="smoke@veriprops.test", customer_name="Live Smoke",
        title="Veriprops live smoke", description="Sandbox round trip; never paid",
    ))
    check(urlparse(url).scheme == "https", f"checkout URL is not https: {url!r}")

    charge = await gateway.get_charge(reference)
    status = charge.status if charge else None
    check(status in (None, GatewayChargeStatus.PENDING), f"an unpaid charge reads {status}")
    return f"checkout on {urlparse(url).netloc}; the unpaid charge reads {status.value if status else 'unknown'}"


async def probe_paystack(_options: Options) -> str:
    return await _collection(IntegratedPlatform.PAYSTACK, "PAYSTACK_SECRET_KEY")


async def probe_flutterwave(_options: Options) -> str:
    return await _collection(IntegratedPlatform.FLUTTERWAVE, "FLUTTERWAVE_SECRET_KEY")


# ─── Payments: transfers ────────────────────────────────────────────────────────────

# Flutterwave documents this account (Access Bank) for test-mode resolves and transfers.
# Paystack documents none, so its account is passed in (`--paystack-bank code:number`).
_FLUTTERWAVE_TEST_ACCOUNT = ("044", "0690000032")
_TRANSFER_MINOR = 10_000  # ₦100


async def _transfers(platform: IntegratedPlatform, key: str, account: Optional[tuple], options: Options) -> str:
    """Banks → resolve → fee; with --send-transfer also send ₦100, find it again by our
    reference, and check the gateway refuses a second transfer under the same one."""
    from main.appodus_utils.integrations.payment.gateway.interface import ITransferGateway
    from main.appodus_utils.integrations.payment.gateway.models import TransferRequest

    _require(key)
    if account is None:
        raise Skip("no test bank account (pass --paystack-bank bank_code:account_number)")
    # `for_platform`, not `transfers()`: under PAYMENT_STUB_MODE the latter hands out the stub,
    # which would "pass" without the gateway ever being called.
    gateway = _payment_gateways().for_platform(platform)
    check(isinstance(gateway, ITransferGateway), f"{platform.value} cannot send transfers")

    banks = await gateway.list_banks(TransactionCurrency.NGN)
    check(banks, "the bank list is empty")
    bank_code, account_number = account
    resolved = await gateway.resolve_account(bank_code, account_number)
    check(resolved is not None, f"the gateway knows no account {bank_code}/{account_number}")
    fee = await gateway.quote_fee(_TRANSFER_MINOR, TransactionCurrency.NGN)
    check(fee >= 0, f"a negative fee: {fee}")
    detail = f"{len(banks)} banks; resolved {resolved.account_name!r}; fee {fee} kobo on ₦100"
    if not options.send_transfer:
        return detail + "; no transfer sent (pass --send-transfer)"

    request = TransferRequest(
        reference=_smoke_reference("tr"), amount_minor=_TRANSFER_MINOR, currency=TransactionCurrency.NGN,
        bank_code=bank_code, account_number=account_number, account_name=resolved.account_name,
        narration="Veriprops live smoke",
    )
    await gateway.send_transfer(request)
    found = await gateway.get_transfer(request.reference)
    check(found is not None, "the transfer cannot be found by our reference")
    try:
        await gateway.send_transfer(request)
    except IntegrationException:
        duplicate = "refused"
    else:
        raise CheckFailed("a second transfer under the same reference was accepted")
    return f"{detail}; sent {request.reference} ({found.status.value}); a repeat of it was {duplicate}"


def _paystack_account(options: Options) -> Optional[tuple]:
    if not options.paystack_bank:
        return None
    code, _, number = options.paystack_bank.partition(":")
    return code, number


async def probe_paystack_transfers(options: Options) -> str:
    return await _transfers(IntegratedPlatform.PAYSTACK, "PAYSTACK_SECRET_KEY", _paystack_account(options), options)


async def probe_flutterwave_transfers(options: Options) -> str:
    return await _transfers(IntegratedPlatform.FLUTTERWAVE, "FLUTTERWAVE_SECRET_KEY", _FLUTTERWAVE_TEST_ACCOUNT, options)


# ─── Document storage ───────────────────────────────────────────────────────────────


async def probe_s3(_options: Options) -> str:
    """Put an encrypted object, read it through its link and a fresh one, then delete it by
    prefix (erasure's path) and check the link stops working."""
    from main.appodus_utils.integrations.document_storage.factory import DocumentStorageProviderFactory

    _require("AWS_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY")
    storage = di[DocumentStorageProviderFactory].get_active_provider()
    bucket = settings.AWS_S3_BUCKET
    prefix = f"smoke/{secrets.token_hex(8)}/"
    body = b"veriprops live smoke"
    upload_url = await storage.upload(
        f"{prefix}probe.txt", bucket, io.BytesIO(body), {}, encrypted=True, content_type="text/plain",
    )
    deleted = 0
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            for label, url in (("upload link", upload_url),
                               ("fresh link", await storage.get_presigned_url(f"{prefix}probe.txt", bucket))):
                response = await http.get(url)
                check(response.status_code == 200 and response.content == body, f"{label}: HTTP {response.status_code}")
                check(response.headers.get("content-type", "").startswith("text/plain"), f"{label}: wrong content type")
            deleted = await storage.delete_prefix(prefix, bucket)
            check(deleted == 1, f"delete_prefix removed {deleted} objects")
            gone = await http.get(upload_url)
            check(gone.status_code in (403, 404), f"a deleted object still answers HTTP {gone.status_code}")
    finally:
        if not deleted:  # a failed check above must not leave the object in the bucket
            await storage.delete_prefix(prefix, bucket)
    return f"put → read twice → deleted by prefix, in bucket {bucket}"


# ─── Messaging ──────────────────────────────────────────────────────────────────────


async def _send(provider_cls, message) -> str:
    from main.appodus_utils.integrations.messaging.models import MessageStatus

    sent = await di[provider_cls].send_message(message)
    check(sent.status == MessageStatus.SENT, f"status {sent.status}")
    return f"accepted as {sent.provider_id or '(no id)'}; confirm it arrived"


def _email(options: Options):
    from main.app.domain.message.models import UpsertMessageDto
    from main.appodus_utils.integrations.messaging.models import EmailPayload, MessageChannel, MessageRecipient

    to = _recipient(options.email, "--email")
    return UpsertMessageDto(
        channel=MessageChannel.EMAIL, to=MessageRecipient(recipient=to),
        payload=EmailPayload(subject="Veriprops live smoke", text="A sandbox round trip. No action needed.",
                             html="<p>A sandbox round trip. No action needed.</p>"),
    )


async def probe_email_resend(options: Options) -> str:
    from main.appodus_utils.integrations.messaging.providers.email.resend import ResendEmailProvider

    _require("RESEND_API_KEY")
    return await _send(ResendEmailProvider, _email(options))


async def probe_email_mailjet(options: Options) -> str:
    from main.appodus_utils.integrations.messaging.providers.email.mailjet import MailjetEmailProvider

    _require("MAILJET_API_KEY", "MAILJET_API_SECRET")
    return await _send(MailjetEmailProvider, _email(options))


async def probe_email_ses(options: Options) -> str:
    from main.appodus_utils.integrations.messaging.providers.email.aws_ses import AmazonSESEmailProvider

    _require("AWS_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY")
    return await _send(AmazonSESEmailProvider, _email(options))


def _sms(to: str):
    from main.app.domain.message.models import UpsertMessageDto
    from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageRecipient, SmsPayload

    return UpsertMessageDto(
        channel=MessageChannel.SMS, to=MessageRecipient(recipient=to),
        payload=SmsPayload(text="Veriprops live smoke. No action needed.", sender_id=settings.SMS_SENDER_ID),
    )


async def probe_sms_termii(options: Options) -> str:
    from main.appodus_utils.integrations.messaging.providers.sms.termii import TermiiSMSProvider

    _require("TERMII_API_KEY")
    return await _send(TermiiSMSProvider, _sms(_recipient(options.phone, "--phone")))


async def probe_sms_twilio(options: Options) -> str:
    from main.appodus_utils.integrations.messaging.providers.sms.twilio_sms import TwilioSMSProvider

    _require("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER")
    return await _send(TwilioSMSProvider, _sms(_recipient(options.intl_phone, "--intl-phone")))


# Meta ships this template, approved, on every business account and its test number.
_META_HELLO_TEMPLATE = ("hello_world", "en_US")


async def probe_whatsapp(options: Options) -> str:
    """The number's health and the template directory (the ids and token are right), then
    Meta's own approved template to an allow-listed handset."""
    from main.app.domain.message.models import UpsertMessageDto
    from main.appodus_utils.integrations.messaging.models import MessageChannel, MessageRecipient, WhatsappPayload
    from main.appodus_utils.integrations.messaging.providers.whatsapp.directory import (
        META_STATUS_APPROVED,
        MetaNumberDirectory,
        MetaTemplateDirectory,
    )
    from main.appodus_utils.integrations.messaging.providers.whatsapp.whatsapp_business import WhatsAppBusinessProvider

    _require("WHATSAPP_BUSINESS_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_BUSINESS_ACCOUNT_ID")
    health = await MetaNumberDirectory().fetch_number_health()
    templates = await MetaTemplateDirectory().list_templates()
    approved = sum(1 for t in templates if t.status == META_STATUS_APPROVED)
    detail = f"number quality {health.quality_rating}; {approved}/{len(templates)} templates approved"
    if not options.whatsapp:
        return detail + "; nothing sent (pass --whatsapp)"
    name, language = _META_HELLO_TEMPLATE
    message = UpsertMessageDto(
        channel=MessageChannel.WHATSAPP, to=MessageRecipient(recipient=options.whatsapp),
        payload=WhatsappPayload(template_name=name, language_code=language),
    )
    return f"{detail}; {await _send(WhatsAppBusinessProvider, message)}"


# ─── Intent ─────────────────────────────────────────────────────────────────────────


def _intent_cases():
    from main.appodus_utils.integrations.intent.models import BotIntent

    return (
        ("How much does it cost to verify a property?", BotIntent.PRICING),
        ("I want to verify a plot of land in Lekki before I pay for it", BotIntent.START_VERIFICATION),
        ("What is the status of my verification?", BotIntent.CHECK_STATUS),
        ("Please let me talk to a real person", BotIntent.TALK_TO_HUMAN),
        ("I want my money back and cancel the order", BotIntent.REFUND_OR_CANCELLATION),
    )


INTENT_CASES = _intent_cases()


def _active_classifier():
    from main.appodus_utils.integrations.intent.factory import IntentClassifierFactory
    return di[IntentClassifierFactory].get_active_classifier()


async def probe_intent(_options: Options) -> str:
    """Five fixed utterances must come back as their intents. The classifier turns any fault
    into UNKNOWN (a human takes over), so a bad key shows up here as misreads, not errors."""
    _require("INTENT_API_KEY")
    classifier = _active_classifier()
    if classifier.platform == IntentProvider.STUB:
        raise Skip("INTENT_PROVIDER is the stub")
    misread = []
    for text, expected in INTENT_CASES:
        result = await classifier.classify(text)
        if result.intent != expected:
            misread.append(f"{expected.value} read as {result.intent.value}")
    check(not misread, "; ".join(misread))
    return f"{len(INTENT_CASES)}/{len(INTENT_CASES)} utterances read correctly on {classifier.platform.value}"


# ─── Identity and address ───────────────────────────────────────────────────────────

# Dojah's documented sandbox BVN; every other number is unknown to the sandbox.
_DOJAH_SANDBOX_BVN = "22222222222"
_UNKNOWN_BVN = "00000000000"


async def probe_dojah(options: Options) -> str:
    """Liveness + selfie match on the sandbox BVN must reach a decision, and an unknown number
    must fail — not raise, which would read as an outage."""
    from main.appodus_utils.integrations.kyc.factory import KycProviderFactory
    from main.appodus_utils.integrations.kyc.models import BvnVerificationRequest, KycProvider, KycResultStatus

    _require("DOJAH_APP_ID", "DOJAH_PRIVATE_KEY")
    if not options.selfie:
        raise Skip("no selfie (pass --selfie path/to/face.jpg)")
    selfie = SecretStr(base64.b64encode(options.selfie.read_bytes()).decode())
    dojah = di[KycProviderFactory].get_provider(KycProvider.DOJAH)

    known = await dojah.verify_bvn(BvnVerificationRequest(
        bvn=_DOJAH_SANDBOX_BVN, first_name="John", last_name="Doe", selfie_image=selfie,
    ))
    check(known.status in (KycResultStatus.VERIFIED, KycResultStatus.NEEDS_REVIEW), (
        f"the sandbox BVN came back {known.status.value}: {known.summary}"
    ))
    unknown = await dojah.verify_bvn(BvnVerificationRequest(
        bvn=_UNKNOWN_BVN, first_name="John", last_name="Doe", selfie_image=selfie,
    ))
    check(unknown.status == KycResultStatus.FAILED, f"an unknown BVN came back {unknown.status.value}")
    return f"sandbox BVN → {known.status.value} (score {known.score}); unknown BVN → FAILED"


async def probe_places(_options: Options) -> str:
    """Suggest "Lekki" in Nigeria, then resolve the first suggestion in the same session."""
    from main.appodus_utils.integrations.geocoding.google_places.google_geocoder import GooglePlacesGeocoder

    _require("GOOGLE_PLACES_API_KEY")
    geocoder = di[GooglePlacesGeocoder]
    session = str(uuid.uuid4())
    suggestions = await geocoder.autocomplete("Lekki", country="NG", session_token=session)
    check(suggestions, "no suggestions for 'Lekki'")
    place = await geocoder.geocode(suggestions[0].place_id, session_token=session)
    check(place is not None, f"the suggested place {suggestions[0].place_id} does not resolve")
    return f"{len(suggestions)} suggestions; {place.address} at {place.latitude:.4f},{place.longitude:.4f}"


# ─── The catalogue and the runner ───────────────────────────────────────────────────

PROBES: List[Probe] = [
    Probe("paystack", "hosted checkout opens; an unpaid charge reads pending", probe_paystack),
    Probe("flutterwave", "hosted checkout opens; an unpaid charge reads pending", probe_flutterwave),
    Probe("paystack_transfers", "banks, resolve, fee (+ ₦100 transfer with --send-transfer)", probe_paystack_transfers),
    Probe("flutterwave_transfers", "banks, resolve, fee (+ ₦100 transfer with --send-transfer)",
          probe_flutterwave_transfers),
    Probe("s3", "put, read, fresh link, delete by prefix", probe_s3),
    Probe("email_resend", "one email to --email", probe_email_resend),
    Probe("email_mailjet", "one email to --email", probe_email_mailjet),
    Probe("email_ses", "one email to --email", probe_email_ses),
    Probe("sms_termii", "one SMS to --phone", probe_sms_termii),
    Probe("sms_twilio", "one SMS to --intl-phone", probe_sms_twilio),
    Probe("whatsapp", "number health, template directory, hello_world to --whatsapp", probe_whatsapp),
    Probe("intent", "five fixed utterances", probe_intent),
    Probe("dojah", "liveness + BVN selfie match; an unknown BVN fails", probe_dojah),
    Probe("places", "suggest, then resolve, in one session", probe_places),
]


def select(names: Optional[Sequence[str]]) -> List[Probe]:
    if not names:
        return list(PROBES)
    known = {p.name for p in PROBES}
    unknown = [n for n in names if n not in known]
    if unknown:
        raise SystemExit(f"Unknown probe(s): {', '.join(unknown)}. Known: {', '.join(sorted(known))}")
    return [p for p in PROBES if p.name in set(names)]


async def run_probes(probes: Sequence[Probe], options: Options) -> List[Result]:
    results = []
    for probe in probes:
        try:
            results.append(Result(probe.name, Outcome.PASS, await probe.run(options)))
        except Skip as skip:
            results.append(Result(probe.name, Outcome.SKIP, str(skip)))
        except Exception as exc:  # a probe's own failure is its result, never the run's crash
            results.append(Result(probe.name, Outcome.FAIL, f"{type(exc).__name__}: {exc}"))
        print(f"{results[-1].outcome.value:4}  {probe.name:22}  {results[-1].detail}", flush=True)
    return results


EXIT_FAILED = 1
EXIT_INCOMPLETE = 3


def exit_code(results: Sequence[Result]) -> int:
    """0 only when every selected probe passed; a skipped probe proved nothing."""
    if any(r.outcome == Outcome.FAIL for r in results):
        return EXIT_FAILED
    if any(r.outcome == Outcome.SKIP for r in results):
        return EXIT_INCOMPLETE
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated probe names (default: all)")
    parser.add_argument("--list", action="store_true", help="list the probes and exit")
    parser.add_argument("--email")
    parser.add_argument("--phone", help="a Nigerian handset in E.164 (+234…), for Termii")
    parser.add_argument("--intl-phone", help="a non-Nigerian handset in E.164, for Twilio")
    parser.add_argument("--whatsapp", help="digits only; allow-listed on Meta's test number")
    parser.add_argument("--selfie", type=Path, help="a JPEG of a real, live face, for Dojah")
    parser.add_argument("--paystack-bank", help="bank_code:account_number of a Paystack test account")
    parser.add_argument("--send-transfer", action="store_true", help="send ₦100 on each transfer gateway")
    args = parser.parse_args(argv)

    if args.list:
        for probe in PROBES:
            print(f"{probe.name:22}  {probe.summary}")
        return 0

    refused = refusal(settings, os.environ.get("APPODUS_ACTIVE_ENV"))
    if refused:
        print(f"Refused: {refused}", file=sys.stderr)
        return 2

    probes = select(args.only.split(",") if args.only else None)
    options = Options(
        email=args.email, phone=args.phone, intl_phone=args.intl_phone, whatsapp=args.whatsapp,
        selfie=args.selfie, paystack_bank=args.paystack_bank, send_transfer=args.send_transfer,
    )
    results = asyncio.run(run_probes(probes, options))
    counts = {o: sum(1 for r in results if r.outcome == o) for o in Outcome}
    print(f"\n{counts[Outcome.PASS]} passed, {counts[Outcome.FAIL]} failed, {counts[Outcome.SKIP]} skipped")
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
