"""Stage — WhatsApp channel (S1–S11, PRD §26).

Drives the channel over HTTP the way the outside world does. Six things here cannot be
proved by unit tests, and all of them are load-bearing:

* **The webhook is the real entry point.** It is signed with a real HMAC over the raw
  body, so this stage signs its own fixtures rather than injecting through the dev door.
  A tampered body must be refused.
* **Redelivery is safe in the database, not just in a mock.** Meta retries until it gets a
  2xx; the unique ``wamid`` index is what turns a retry into a no-op, and only a live
  Postgres can demonstrate that.
* **A handoff link really pays.** §26.10 calls intake→payment the channel's most important
  number, so the stage carries a `pay` token all the way to a PAID verification.
* **An agent's console reply really leaves the building.** For two commits it did not: the
  message was written into the thread and delivered nowhere, and this stage asserted only
  that the thread flipped to `HUMAN` — which passed the whole time. The outbox assertion
  is the one that would have caught it.
* **The customer is answered whatever they send.** §26.6.3's three rows are exercised
  against the real ingestion path, including the photo case that used to be answered
  with "Sorry, I didn't quite get that".
* **Erasure actually reaches the channel.** The channel keys on a phone number rather than a
  user id, so "the account is erased" and "the number still resolves to a customer" can both
  be true at once. A mock proves the UPDATEs are issued; only a live stack proves they reach
  the rows the bot reads on the *next* message (§26.8, WA-42).

Runs late: it needs a customer who can own a case, and it creates its own payable
verification rather than disturbing the one earlier stages built.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid

from .harness import (
    MINIMAL_PNG,
    QA_PASSWORD,
    TEST_OTP,
    Ctx,
    check,
    client,
    consent_version_for,
    idem_key,
    login_status,
    pin_cookie_header,
    signup_fresh_user,
    stub_pay,
    warn,
)
from .stage_execution import ROLE_PAYLOADS as _ROLE_PAYLOADS

# The webhook secret is Doppler-managed and absent from committed env files, so the
# signature checks run only when the operator started the backend with one and exported
# the same value here — the same opt-in shape as ENABLE_OUT_MESSAGING for the email
# stage. Everything downstream of the webhook is exercised either way, through the dev
# injection endpoint.
_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET_KEY", "")
_VERIFY_TOKEN = os.environ.get("WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN", "")
_PLACEHOLDERS = {"", "CHANGE_ME"}
# A fresh number per run. `/dev/reset` clears the database, but the OTP service's
# resend counters live in Redis/KV and are keyed on the **number**, not the account — so
# a fixed number made the second run inside the lockout window fail on a rate limit that
# has nothing to do with what the stage is testing.
_CUSTOMER_PHONE = f"23480{uuid.uuid4().int % 10**8:08d}"


def _envelope(wamid: str, text: str, phone: str = _CUSTOMER_PHONE) -> bytes:
    """A Meta Cloud API inbound-message webhook body, byte-for-byte as posted."""
    return json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "PNID"},
            "contacts": [{"wa_id": phone, "profile": {"name": "Ada"}}],
            "messages": [{
                "from": phone, "id": wamid, "timestamp": str(int(time.time())),
                "type": "text", "text": {"body": text},
            }],
        }}]}],
    }).encode()


def _sign(body: bytes, secret: str = "") -> str:
    key = (secret or _APP_SECRET or "").encode()
    return "sha256=" + hmac.new(key, body, hashlib.sha256).hexdigest()


def run(ctx: Ctx) -> None:
    root = ctx.root

    # ── S1: one config source for the official number (§26.1.2, WA-02) ──────────
    cfg = root.get("/config/public").json()["data"]
    check("public config serves the official WhatsApp number (§26.1.2)",
          cfg.get("whatsappNumber", "").isdigit() and len(cfg["whatsappNumber"]) > 10,
          f"number={cfg.get('whatsappNumber')}")
    check("the number is also served in its human-readable form",
          cfg.get("whatsappDisplayNumber", "").startswith("+"),
          f"display={cfg.get('whatsappDisplayNumber')}")
    check("the widget kill switch is exposed to the frontend (§26.4.1)",
          isinstance(cfg.get("whatsappWidgetEnabled"), bool))

    # ── S2: the webhook is the front door, and the signature is the auth ───────
    signed_delivery = _APP_SECRET not in _PLACEHOLDERS and _VERIFY_TOKEN not in _PLACEHOLDERS
    if signed_delivery:
        _run_webhook_checks(ctx)
    else:
        warn("WhatsApp webhook signature checks skipped",
             "export WHATSAPP_APP_SECRET_KEY + WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN "
             "(the same values the backend is running with) to exercise them")
        # Still get a message into the console, through the dev door rather than Meta's.
        root.post("/dev/whatsapp/inbound", json={
            "fromPhone": _CUSTOMER_PHONE, "senderName": "Ada",
            "text": "How much for a Lagos land check?",
        }).raise_for_status()

    # ── S2: inbound reaches the admin console, policed like web chat ───────────
    _run_console_checks(ctx)

    # ── S3: a handoff link carries a real payment to PAID ─────────────────────
    _run_handoff_checks(ctx)

    # ── S4: the number becomes an identity, and stops being one on unlink ─────
    _run_linking_checks(ctx)

    # ── §26.7: the template registry the launch gate reads ────────────────────
    _run_template_registry_checks(ctx)

    # ── S5: the bot actually answers, and refuses what it must ───────────────
    _run_bot_checks(ctx)

    # ── S6: a chat intake becomes a real draft on the website ────────────────
    _run_intake_checks(ctx)

    # ── S7: §26.6.3 — every non-text type answered per the table ──────────────
    _run_media_checks(ctx)

    # ── S8: §26.4.6 consent, and the milestones it gates ──────────────────────
    # `_run_media_checks` leaves the customer unlinked (the 1:1 rule), so these two
    # re-link on their own number before touching anything case-scoped.
    consent_phone = _run_consent_checks(ctx)
    _run_milestone_checks(ctx, consent_phone)

    # ── S9: §26.4.5 — one delegate, status only, revocable ────────────────────
    _run_delegate_checks(ctx)

    # ── S10.0: §26.3.4's other two handoffs, now reachable from a conversation ─
    _run_pay_report_handoff_checks(ctx)

    # ── S10: §26.10 — the metrics move when real traffic moves them ───────
    _run_channel_analytics_checks(ctx)

    # ── S11: §26.6.5's fallback, drilled on a live stack ──────────────────
    _run_failure_drill_checks(ctx)

    # ── S11: §26.8 — the consent ledger exports, and erasure reaches the channel.
    # Last, because it revokes a link and drops a session the analytics above count.
    _run_channel_erasure_checks(ctx)


def _run_webhook_checks(ctx: Ctx) -> None:
    root = ctx.root

    # The subscription handshake Meta performs before it will deliver anything.
    challenge = str(uuid.uuid4().int % 10**10)
    r = root.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": _VERIFY_TOKEN, "hub.challenge": challenge,
    })
    check("webhook echoes Meta's subscription challenge (§26.3.3)",
          r.status_code == 200 and challenge in r.text, f"http {r.status_code}: {r.text[:120]}")

    r = root.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "not-the-token", "hub.challenge": challenge,
    })
    check("webhook refuses a handshake with the wrong verify token",
          r.status_code in (401, 403), f"http {r.status_code}")

    # A genuine signed delivery.
    wamid = f"wamid.e2e.{uuid.uuid4().hex[:12]}"
    body = _envelope(wamid, "How much for a Lagos land check?")
    r = root.post("/webhooks/whatsapp", content=body,
                  headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(body)})
    check("signed Meta delivery accepted (§26.3.3, WA-09)", r.status_code == 200,
          f"http {r.status_code}: {r.text[:160]}")
    ctx.wa_wamid = wamid

    # The signature covers the raw bytes: editing the body must invalidate it.
    tampered = _envelope(wamid + "x", "How much for a Lagos land check?")
    r = root.post("/webhooks/whatsapp", content=tampered,
                  headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(body)})
    check("webhook rejects a body that does not match its signature",
          r.status_code == 403, f"http {r.status_code}")

    r = root.post("/webhooks/whatsapp", content=body,
                  headers={"Content-Type": "application/json"})
    check("webhook rejects an unsigned delivery (the signature IS the auth)",
          r.status_code == 403, f"http {r.status_code}")

    r = root.post("/webhooks/whatsapp", content=body, headers={
        "Content-Type": "application/json",
        "X-Hub-Signature-256": _sign(body, "an-attackers-secret"),
    })
    check("webhook rejects a delivery signed with the wrong secret",
          r.status_code == 403, f"http {r.status_code}")

    # Meta retries until it gets a 2xx. The unique wamid is what makes that safe.
    r = root.post("/webhooks/whatsapp", content=body,
                  headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sign(body)})
    check("a redelivered message is acknowledged, not rejected (Meta would disable the "
          "subscription on a non-2xx)", r.status_code == 200, f"http {r.status_code}")

    # A signed but unparseable body must also be acknowledged, never 500.
    junk = b"{not json"
    r = root.post("/webhooks/whatsapp", content=junk, headers={
        "Content-Type": "application/json", "X-Hub-Signature-256": _sign(junk)})
    check("a signed but malformed body is acknowledged and ignored", r.status_code == 200,
          f"http {r.status_code}")


def _run_console_checks(ctx: Ctx) -> None:
    root, admin = ctx.root, ctx.admin

    # Exactly one console message for the redelivered wamid (the dedup, proved end to end).
    threads = admin.get("/chat/conversations").json()["data"]
    # Selected by this run's own number: a WhatsApp thread from an earlier run would
    # otherwise be picked up and asserted against.
    wa_threads = [t for t in threads if t.get("channel") == "WHATSAPP"
                  and str(t.get("externalRef", "")).endswith(_CUSTOMER_PHONE[-10:])]
    check("a WhatsApp enquiry opens a thread in the admin console (Decision K)",
          len(wa_threads) >= 1, f"threads={len(wa_threads)}")

    if not wa_threads:
        return
    thread = wa_threads[0]
    check("the thread is keyed on the sender's number, not an account (§26.4.4)",
          str(thread.get("externalRef", "")).endswith(_CUSTOMER_PHONE[-10:]),
          f"externalRef={thread.get('externalRef')}")

    msgs = admin.get(f"/chat/conversations/{thread['id']}/messages").json()["data"]["items"]
    check("console messages are labelled with the surface they arrived on (§26.3.3)",
          all(m.get("source") == "WHATSAPP" for m in msgs), f"sources={[m.get('source') for m in msgs]}")

    if getattr(ctx, "wa_wamid", ""):
        enquiry = [m for m in msgs if "Lagos land check" in m["body"]]
        check("a Meta redelivery produced exactly one console message (unique wamid)",
              len(enquiry) == 1, f"copies={len(enquiry)}")

    # WA-13: WhatsApp text runs the *same* fraud scan as web chat.
    root.post("/dev/whatsapp/inbound", json={
        "fromPhone": _CUSTOMER_PHONE, "text": "just call me on 08031234567 instead",
    }).raise_for_status()
    held = admin.get("/admin/messages/held").json()["data"]["items"]
    wa_held = [m for m in held if m.get("source") == "WHATSAPP"]
    check("WhatsApp text is held by the same fraud scan as web chat (WA-13)",
          any("08031234567" in m["body"] for m in wa_held), f"held={len(wa_held)}")

    # §26.6.3: non-text is journalled and labelled, never silently dropped.
    root.post("/dev/whatsapp/inbound", json={"fromPhone": _CUSTOMER_PHONE, "kind": "AUDIO"}).raise_for_status()
    msgs = admin.get(f"/chat/conversations/{thread['id']}/messages").json()["data"]["items"]
    check("a voice note reaches the console labelled, never dropped (§26.6.3)",
          any("voice note" in m["body"] for m in msgs))

    # The stub transport is what CI sends through; the outbox is its assertion surface.
    outbox = root.get("/dev/whatsapp/outbox").json()["data"]
    check("the stub transport exposes an outbox for assertions (D43)", "messages" in outbox)


def _run_handoff_checks(ctx: Ctx) -> None:
    root, customer = ctx.root, ctx.customer

    # A payable case of this stage's own, so the earlier stages' verification is untouched.
    case_id = _create_payable_case(ctx)
    if not case_id:
        return

    customer_id = customer.get("/users/auth/sessions/current").json()["data"]["user"]["id"]

    def mint(intent: str) -> str:
        return root.post("/dev/whatsapp/handoff-token", json={
            "caseId": case_id, "customerId": customer_id, "intent": intent,
        }).json()["data"]["token"]

    # 1. Redeeming lands the customer on their case, with context (§26.4.2).
    token = mint("pay")
    holder = client()
    r = holder.post(f"/public/wa/handoff/pay/{token}/redeem")
    check("a pay link redeems without a session (§26.5 — the token is the authorization)",
          r.status_code == 200, f"http {r.status_code}: {r.text[:160]}")
    # The grant is a Secure cookie and this runs over plain http (see the harness).
    pin_cookie_header(holder)
    context = r.json()["data"]
    check("the landing is told which case it is picking up (§26.4.2)",
          context.get("vid", "").startswith("VP-"), f"context={context}")
    check("the landing is told what is owed", (context.get("amountDueMinor") or 0) > 0)

    # 2. A forwarded copy is dead — a different client, same link.
    r = client().post(f"/public/wa/handoff/pay/{token}/redeem")
    check("a forwarded copy of a spent link is refused (§26.5 single-use)",
          r.status_code == 404, f"http {r.status_code}")

    # 3. …but the customer who redeemed it may reload their own page (D51).
    r = holder.post(f"/public/wa/handoff/pay/{token}/redeem")
    check("the original holder can reload their landing (D51 grant)",
          r.status_code == 200, f"http {r.status_code}: {r.text[:160]}")

    # 4. A link is scoped to one action: a report link is not a payment authorization.
    r = client().post(f"/public/wa/handoff/pay/{mint('report')}/redeem")
    check("a report link presented at the pay landing is refused (§26.5 scope)",
          r.status_code == 404, f"http {r.status_code}")

    # 5. Garbage and a spent link are indistinguishable from outside.
    r = client().post("/public/wa/handoff/pay/not-a-real-token/redeem")
    check("an invalid link fails exactly like a spent one (no oracle)",
          r.status_code == 404, f"http {r.status_code}")

    # 6. The seam that matters: the handoff actually pays (§26.10).
    r = holder.post("/public/wa/handoff/pay/initiate")
    check("the grant starts a real payment for the case it names (§26.4.2, Decision A)",
          r.status_code == 200, f"http {r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        return
    payment = r.json()["data"]
    check("the handoff payment carries a gateway reference", bool(payment.get("txRef")))

    r = customer.post("/payments/stub/confirm",
                      json={"txRef": payment["txRef"], "succeeded": True})
    check("a WhatsApp-originated payment completes (§26.10 seam conversion)",
          r.status_code == 200 and r.json()["data"].get("processed") is True,
          f"http {r.status_code}: {r.text[:160]}")
    status = customer.get(f"/verifications/{case_id}").json()["data"]["status"]
    check("the case reached PAID through the WhatsApp handoff", status == "PAID",
          f"status={status}")

    # 7. Without a grant, the payment endpoint authorizes nothing.
    r = client().post("/public/wa/handoff/pay/initiate")
    check("payment initiation is refused without a grant", r.status_code == 404,
          f"http {r.status_code}")


def _run_linking_checks(ctx: Ctx) -> None:
    """§26.4.4 account linking, end to end on the stub transport (WA-23/WA-24/WA-25).

    Three things cannot be proved without a live stack, and all three are the point of
    the slice: the code really goes out over **WhatsApp** (the stub outbox is the
    evidence), the console thread this number has been talking in really gains an owner
    rather than a second thread appearing, and unlinking really releases the number so
    another account could claim it.
    """
    root, customer, admin = ctx.root, ctx.customer, ctx.admin

    link = customer.get("/channel/whatsapp/link/me").json()["data"]
    check("a fresh account starts with no WhatsApp link (§26.4.4)",
          link.get("status") != "ACTIVE" and not link.get("phoneE164"), f"link={link}")

    root.delete("/dev/whatsapp/outbox")
    r = customer.post("/channel/whatsapp/link/me/start",
                      json={"phoneE164": f"+{_CUSTOMER_PHONE}"})
    check("starting a link is accepted (§26.4.4, WA-23)", r.status_code == 200,
          f"http {r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        return

    # D46: the linking code travels over WhatsApp itself, not SMS. The stub outbox is
    # the only place that can prove it — a unit test mocks the transport away.
    sent = root.get("/dev/whatsapp/outbox", params={"recipient": _CUSTOMER_PHONE}).json()["data"]
    messages = sent.get("messages", [])
    check("the linking code goes out over WhatsApp, not SMS (D46)",
          bool(messages), f"outbox={sent}")
    check("it carries the deterministic code, to the number being linked",
          any(TEST_OTP in (m.get("text") or "") for m in messages),
          f"bodies={[(m.get('text') or '')[:60] for m in messages]}")

    # §26.7/D59b: an OTP to a number that has never messaged us is outside Meta's 24-hour
    # window, so it must go as the approved **template** — free text would be rejected
    # live. The stub records both halves, which is the only place this is observable.
    templated = [m for m in messages if m.get("templateName") == "otp_auth"]
    check("the linking OTP is sent as the §26.7 `otp_auth` template, not free text",
          bool(templated), f"templates={[m.get('templateName') for m in messages]}")
    if templated:
        sent_template = templated[-1]
        variables = sent_template.get("templateVariables") or {}
        check("the code is Meta's first positional body parameter",
              variables.get("1") == TEST_OTP, f"variables={variables}")
        # Meta mandates an OTP button on authentication templates and rejects a send
        # without the matching component, so the button parameter is part of delivery.
        check("the authentication template carries its mandatory OTP button parameter",
              sent_template.get("templateButtonParameter") == TEST_OTP,
              f"button={sent_template.get('templateButtonParameter')}")

    check("the customer-facing brand is the display name, not the lowercase slug",
          any((m.get("text") or "").startswith("Veriprops") for m in messages),
          f"bodies={[(m.get('text') or '')[:30] for m in messages]}")

    # A number mid-attempt is not a link: nothing may resolve to the account yet.
    pending = customer.get("/channel/whatsapp/link/me").json()["data"]
    check("a pending attempt is not yet a link (§26.4.4)", pending.get("status") == "PENDING",
          f"status={pending.get('status')}")

    r = customer.post("/channel/whatsapp/link/me/confirm",
                      json={"phoneE164": f"+{_CUSTOMER_PHONE}", "code": "000000"})
    check("a wrong code does not link the number", r.status_code >= 400, f"http {r.status_code}")

    r = customer.post("/channel/whatsapp/link/me/confirm",
                      json={"phoneE164": f"+{_CUSTOMER_PHONE}", "code": TEST_OTP})
    check("the right code links the number (deterministic OTP)", r.status_code == 200,
          f"http {r.status_code}: {r.text[:200]}")
    linked = customer.get("/channel/whatsapp/link/me").json()["data"]
    check("the account now shows an active WhatsApp link",
          linked.get("status") == "ACTIVE" and linked.get("phoneE164", "").endswith(
              _CUSTOMER_PHONE[-10:]), f"link={linked}")

    # §26.8: one conversation object per person — the *existing* thread gains an owner.
    threads = admin.get("/chat/conversations").json()["data"]
    wa_threads = [t for t in threads if t.get("channel") == "WHATSAPP"
                  and str(t.get("externalRef", "")).endswith(_CUSTOMER_PHONE[-10:])]
    check("linking adopts the existing thread instead of opening a second one (§26.8)",
          len(wa_threads) == 1, f"threads={len(wa_threads)}")

    # WA-25: unlinking releases the number and the thread goes cold.
    r = customer.delete("/channel/whatsapp/link/me")
    check("the customer can unlink their number (WA-25)", r.status_code == 200,
          f"http {r.status_code}: {r.text[:160]}")
    after = customer.get("/channel/whatsapp/link/me").json()["data"]
    check("an unlinked account holds no number at all — a retained one would lock that "
          "number out of every other account forever",
          after.get("status") != "ACTIVE" and not after.get("phoneE164"), f"link={after}")

    # An unlinked account can start over. Deliberately a *different* number: the OTP
    # service caps resends per number, so re-sending to the one just used would be
    # refused by that cap rather than by anything about linking — the row's release is
    # proved by the unique constraints in the unit and migration checks.
    r = customer.post("/channel/whatsapp/link/me/start",
                      json={"phoneE164": f"+23481{uuid.uuid4().int % 10**8:08d}"})
    check("an unlinked account can start a fresh link (WA-25)", r.status_code == 200,
          f"http {r.status_code}: {r.text[:200]}")
    customer.delete("/channel/whatsapp/link/me")


_PRD_TEMPLATES = {
    "otp_auth", "payment_confirmed", "verification_started", "inspection_complete",
    "report_ready", "window_reopen", "delegate_status",
}


def _run_template_registry_checks(ctx: Ctx) -> None:
    """§26.7 template registry (WA-15/WA-41).

    The §26.11 launch gate turns on "all §26.7 templates approved", so the operational
    question is whether an admin can actually see that answer. Under the stub the
    directory reports the declared set as approved, which is what makes the whole channel
    demoable without Meta — the live directory is the same interface behind a different
    transport.
    """
    admin, customer = ctx.admin, ctx.customer

    registry = admin.get("/admin/config/whatsapp-templates").json()["data"]
    check("the admin registry lists all seven §26.7 templates (WA-15)",
          {t["name"] for t in registry} == _PRD_TEMPLATES,
          f"names={sorted(t['name'] for t in registry)}")
    otp = next((t for t in registry if t["name"] == "otp_auth"), {})
    check("each row carries its category and ordered parameters",
          otp.get("category") == "AUTHENTICATION" and otp.get("parameters") == ["OTP", "VALIDITY"],
          f"otp={otp}")

    result = admin.post("/admin/config/whatsapp-templates/sync").json()["data"]
    check("syncing reads every declared template's status back (WA-41)",
          result.get("synced") == len(_PRD_TEMPLATES), f"result={result}")

    synced = admin.get("/admin/config/whatsapp-templates").json()["data"]
    check("the synced status is persisted for the launch-gate view",
          all(t["status"] == "APPROVED" for t in synced),
          f"statuses={sorted({t['status'] for t in synced})}")
    check("a synced row records when it was last checked",
          all(t.get("lastSyncedAt") for t in synced))

    # The registry is operational configuration, not customer-visible state.
    r = customer.get("/admin/config/whatsapp-templates")
    check("a customer cannot read the template registry (CONFIGURE_SYSTEM)",
          r.status_code == 403, f"http {r.status_code}")


def _run_bot_checks(ctx: Ctx) -> None:
    """The bot engine over the wire (§26.6, WA-11/WA-39).

    Unit tests already pin the gauntlet's branching. What only a live stack proves is that
    a message posted at the webhook comes back out of the **stub transport** as a real
    outbound reply — the whole path through ingestion, the session row, the classifier
    facade, the conversation mirror and the provider. Three of the four faults that killed
    the outbound path before were invisible to unit tests for exactly that reason.

    A fresh number, so the welcome is genuinely a first contact: §26.6.1 short-circuits
    every other rule, and asserting an answer on a number this stage already used would
    silently test nothing.
    """
    root, admin = ctx.root, ctx.admin
    phone = f"23480{uuid.uuid4().int % 10**8:08d}"

    def say(text: str, kind: str = "TEXT") -> list[dict]:
        """Deliver a message and return whatever the stub sent back to this number."""
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        payload = {"fromPhone": phone, "text": text} if kind == "TEXT" else {
            "fromPhone": phone, "kind": kind
        }
        root.post("/dev/whatsapp/inbound", json=payload).raise_for_status()
        messages = root.get("/dev/whatsapp/outbox").json()["data"].get("messages", [])
        # The stub records the Meta `wa_id` form (digits, no '+') under `to`.
        return [m for m in messages if phone[-10:] in str(m.get("to", ""))]

    # §26.6.1 — first contact opens with the disclosure and the payment pledge.
    replies = say("Hi")
    check("the bot answers a first message over the real transport (§26.6.1)",
          len(replies) == 1, f"outbound={len(replies)}")
    if not replies:
        warn("bot drive-through stopped", "no outbound reply to assert against")
        return
    welcome = str(replies[0].get("text", ""))
    check("the welcome discloses that it is a bot (§26.1.4)",
          "automated assistant" in welcome, welcome[:120])
    check("the welcome carries the payment pledge (§26.1.1)",
          "veriprops.ng" in welcome and "address bar" in welcome, welcome[:160])

    # The menu it just offered has to work — a number is the one input it invited.
    replies = say("5")
    pricing = str(replies[0].get("text", "")) if replies else ""
    check("a menu number is answered deterministically (§26.6.1)",
          "₦" in pricing, pricing[:120])
    check("pricing is quoted from the live admin config, not from copy (D54)",
          "per property" in pricing, pricing[:160])

    # §26.6.4 — the guardrail that matters most, over the wire rather than in a unit test.
    replies = say("Is this land genuine? Should I buy it?")
    verdict = str(replies[0].get("text", "")) if replies else ""
    check("the bot refuses to judge a property and routes to a person (§26.6.4)",
          "our verifiers" in verdict or "team" in verdict, verdict[:160])
    check("the refusal renders no verdict of its own (§26.1.3)",
          not any(word in verdict.lower() for word in ("looks genuine", "seems fine", "is safe")),
          verdict[:160])

    # §26.4.3 — an unlinked number is never read case data.
    replies = say("What is the status of my verification?")
    status = str(replies[0].get("text", "")) if replies else ""
    check("an unlinked number is refused case data and offered linking (§26.4.3)",
          "isn't linked" in status, status[:160])

    # §26.6.3 — a voice note is acknowledged and handed over, never ignored. Its own copy
    # since S7: "a team member will listen" is the row's promise, and pooling it with the
    # media the bot merely cannot open lost both the wording and the §26.10 count.
    replies = say("", kind="AUDIO")
    audio = str(replies[0].get("text", "")) if replies else ""
    check("a voice note is acknowledged and handed to a person (§26.6.3)",
          "listen" in audio, audio[:160])

    # D57 — the console is what silences the bot, and the only way back.
    session = admin.get(f"/admin/whatsapp/bot/sessions/{phone}").json()["data"]
    check("the console can read a thread's bot mode (D57)",
          session.get("mode") == "BOT", f"mode={session.get('mode')}")

    threads = admin.get("/chat/conversations").json()["data"]
    thread = next((t for t in threads if str(t.get("externalRef", "")).endswith(phone[-10:])), None)
    check("the bot's own replies are in the console thread (Decision K)", thread is not None)
    if thread:
        msgs = admin.get(f"/chat/conversations/{thread['id']}/messages").json()["data"]["items"]
        check("the console shows what the bot said, as platform copy",
              any(m.get("sender", {}).get("kind") == "SYSTEM" for m in msgs),
              f"kinds={[m.get('sender', {}).get('kind') for m in msgs][:6]}")

        # S7/WA-12 — the check whose absence let a real defect ship: for two commits an
        # agent's reply was written into the thread and delivered nowhere, and this stage
        # asserted only the mode flip below, which passed the whole time.
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        admin.post(f"/chat/conversations/{thread['id']}/messages",
                   json={"body": "Hi, I'll take this one."}).raise_for_status()
        outbound = _outbound_to(ctx, phone)
        check("an agent's console reply reaches the customer over WhatsApp (WA-12)",
              any("I'll take this one" in str(m.get("text", "")) for m in outbound),
              f"outbound={[str(m.get('text'))[:40] for m in outbound]}")

        session = admin.get(f"/admin/whatsapp/bot/sessions/{phone}").json()["data"]
        check("an agent's reply takes the thread off the bot (D57)",
              session.get("mode") == "HUMAN", f"mode={session.get('mode')}")
        check("the console can see that Meta's reply window is open (§26.7)",
              session.get("windowOpen") is True, f"windowOpen={session.get('windowOpen')}")

        _run_window_checks(ctx, phone, thread["id"])

        # With a human on the thread the bot must stay silent — the rule's whole point.
        replies = say("and how much was it again?")
        check("the bot stays silent while a human owns the thread (D57)",
              len(replies) == 0, f"outbound={len(replies)}")

        admin.post(f"/admin/whatsapp/bot/sessions/{phone}/hand-back").raise_for_status()
        session = admin.get(f"/admin/whatsapp/bot/sessions/{phone}").json()["data"]
        check("hand-back returns the thread to the bot (D57)",
              session.get("mode") == "BOT", f"mode={session.get('mode')}")
        replies = say("how much?")
        check("the bot answers again once it is handed back",
              len(replies) == 1, f"outbound={len(replies)}")

    readiness = admin.get("/admin/whatsapp/bot/readiness").json()["data"]
    check("the launch gate can read the channel's configuration (§26.11)",
          readiness.get("whatsappProvider") == "stub"
          and readiness.get("intentProvider") == "stub",
          f"readiness={readiness}")
    check("readiness never carries a credential",
          not any("key" in k.lower() and "configured" not in k.lower() for k in readiness),
          f"keys={list(readiness)}")


def _outbound_to(ctx: Ctx, phone: str) -> list[dict]:
    """What the stub transport has recorded for this number, newest last.

    The stub records Meta's `wa_id` form (digits, no '+') under `to`.
    """
    messages = ctx.root.get("/dev/whatsapp/outbox").json()["data"].get("messages", [])
    return [m for m in messages if phone[-10:] in str(m.get("to", ""))]


def _run_window_checks(ctx: Ctx, phone: str, conversation_id: str) -> None:
    """Meta's 24-hour service window on a late agent reply (§26.7, WA-41).

    Outside the window Meta delivers only an approved template, so the agent's own words
    are **queued** and the `window_reopen` nudge goes instead. Queueing rather than
    dropping is what keeps the thread from dead-ending: it is sticky-`HUMAN` by now (D57),
    so the bot will not answer the customer's next message either.

    Only a live stack proves this. The window is derived from the inbound journal rather
    than a column, so `/dev/whatsapp/rewind-window` ages the journal — the same trick, and
    the same justification, as `/dev/messages/rewind` in the messaging-retry stage.
    """
    root, admin = ctx.root, ctx.admin

    rewound = root.post("/dev/whatsapp/rewind-window", params={"phone": phone, "hours": 25})
    if rewound.status_code != 200:
        warn("WhatsApp 24-hour window checks skipped",
             f"/dev/whatsapp/rewind-window answered http {rewound.status_code}")
        return
    session = admin.get(f"/admin/whatsapp/bot/sessions/{phone}").json()["data"]
    check("an aged conversation reads as outside Meta's window (§26.7)",
          session.get("windowOpen") is False, f"windowOpen={session.get('windowOpen')}")

    root.delete("/dev/whatsapp/outbox").raise_for_status()
    late = "Sorry for the delay — the survey came back clean and I'm sending it over."
    admin.post(f"/chat/conversations/{conversation_id}/messages",
               json={"body": late}).raise_for_status()
    outbound = _outbound_to(ctx, phone)
    check("a late reply goes out as the window_reopen template, not as free text (WA-41)",
          any("replied to your enquiry" in str(m.get("text", "")) for m in outbound),
          f"outbound={[str(m.get('text'))[:60] for m in outbound]}")
    check("Meta is never handed free text it would refuse to deliver",
          not any("survey came back clean" in str(m.get("text", "")) for m in outbound))

    # The console has to say so, or the agent believes their message went.
    msgs = admin.get(f"/chat/conversations/{conversation_id}/messages").json()["data"]["items"]
    queued = [m for m in msgs if m.get("pendingChannelDelivery")]
    check("the queued reply is marked as undelivered in the console (§26.7)",
          any("survey came back clean" in m["body"] for m in queued),
          f"queued={[m['body'][:40] for m in queued]}")

    # One nudge per closed-window episode: three messages must not cost three templates.
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    admin.post(f"/chat/conversations/{conversation_id}/messages",
               json={"body": "Let me know when you're free to talk."}).raise_for_status()
    outbound = _outbound_to(ctx, phone)
    check("a second late reply joins the queue without a second nudge (§26.7)",
          not any("replied to your enquiry" in str(m.get("text", "")) for m in outbound),
          f"outbound={[str(m.get('text'))[:60] for m in outbound]}")

    # The customer answers: the window reopens and the queue flushes, in order.
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    root.post("/dev/whatsapp/inbound", json={
        "fromPhone": phone, "text": "Sorry, just seeing this now",
    }).raise_for_status()
    delivered = [str(m.get("text", "")) for m in _outbound_to(ctx, phone)]
    check("the customer's reply flushes everything the agent queued (§26.7)",
          any("survey came back clean" in t for t in delivered)
          and any("free to talk" in t for t in delivered),
          f"outbound={[t[:50] for t in delivered]}")
    survey_at = next(i for i, t in enumerate(delivered) if "survey came back clean" in t)
    talk_at = next(i for i, t in enumerate(delivered) if "free to talk" in t)
    check("the queue flushes in the order the agent wrote it", survey_at < talk_at,
          f"survey={survey_at} talk={talk_at}")

    msgs = admin.get(f"/chat/conversations/{conversation_id}/messages").json()["data"]["items"]
    check("nothing is left marked undelivered once the queue has flushed",
          not any(m.get("pendingChannelDelivery") for m in msgs))


def _run_media_checks(ctx: Ctx) -> None:
    """§26.6.3 non-text inbound, end to end (WA-06, WA-38).

    The regression this pins is small and embarrassing: image kinds were left out of the
    bot's unreadable set on the assumption the upload handoff would catch them, and the
    handoff had not been built — so a customer photographing their survey plan was
    answered with "Sorry, I didn't quite get that".

    The evidence rule (§26.1.6) is the other half. A document sent here is redirected to
    the upload page rather than accepted, and the console has to say that what arrived is
    not evidence — which only a live stack, reading the real DTO, can show.
    """
    root, admin, customer = ctx.root, ctx.admin, ctx.customer
    phone = f"23480{uuid.uuid4().int % 10**8:08d}"

    def send(kind: str) -> str:
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        root.post("/dev/whatsapp/inbound", json={"fromPhone": phone, "kind": kind}).raise_for_status()
        replies = _outbound_to(ctx, phone)
        return str(replies[0].get("text", "")) if replies else ""

    def say(text: str) -> str:
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        root.post("/dev/whatsapp/inbound", json={"fromPhone": phone, "text": text}).raise_for_status()
        replies = _outbound_to(ctx, phone)
        return str(replies[0].get("text", "")) if replies else ""

    # A fresh number, so §26.6.1's welcome does not answer the turn we are testing.
    root.post("/dev/whatsapp/inbound", json={"fromPhone": phone, "text": "Hi"}).raise_for_status()

    # An unlinked number: the evidence rule still applies, but no upload link — a token
    # names a customer *and* a case, and a phone number alone identifies neither (§26.4.3).
    unlinked = send("IMAGE")
    check("a photo from an unlinked number is answered with the evidence rule (§26.1.6)",
          "verification file" in unlinked, unlinked[:200])
    check("an unlinked number is never handed an upload link (§26.4.3)",
          "/wa/upload/" not in unlinked, unlinked[:200])

    # §26.6.3 row two — a voice note is acknowledged with its own copy, never dropped.
    voice = send("AUDIO")
    check("a voice note is promised a person who will listen (§26.6.3)",
          "listen" in voice, voice[:200])
    session = admin.get(f"/admin/whatsapp/bot/sessions/{phone}").json()["data"]
    check("a voice note is counted under its own escalation reason (§26.10)",
          session.get("lastEscalationReason") == "VOICE_NOTE",
          f"reason={session.get('lastEscalationReason')}")

    # §26.6.3 row three — a pin goes to a person.
    pin = send("LOCATION")
    check("a location pin is acknowledged and routed to a person (§26.6.3)",
          bool(pin) and "team member" in pin, pin[:200])

    # The console's own view: labelled, and labelled as not-evidence.
    threads = admin.get("/chat/conversations").json()["data"]
    thread = next((t for t in threads if str(t.get("externalRef", "")).endswith(phone[-10:])), None)
    check("the media thread is in the console", thread is not None)
    if thread:
        msgs = admin.get(f"/chat/conversations/{thread['id']}/messages").json()["data"]["items"]
        media = [m for m in msgs if m.get("mediaKind")]
        check("non-text inbound carries what it was, for the console to flag (§26.6.3)",
              {m.get("mediaKind") for m in media} >= {"IMAGE", "AUDIO", "LOCATION"},
              f"kinds={[m.get('mediaKind') for m in media]}")
        check("chat media is flagged unofficial — it never enters the file (WA-06)",
              media and all(m.get("unofficialMedia") for m in media),
              f"flags={[m.get('unofficialMedia') for m in media]}")
        check("plain text is not flagged as media",
              all(not m.get("unofficialMedia") for m in msgs if not m.get("mediaKind")))

    # A linked number with a real case: now the upload link can be issued and scoped.
    # The case is the one `_run_handoff_checks` created and paid for on this customer.
    if not _link_number(ctx, phone):
        return
    linked = send("IMAGE")

    # This customer has several cases by now, so the bot must ask which one rather than
    # guess: an `upload` token authorizes writing to exactly one verification, and
    # attaching a document to the wrong file is worse than a question.
    check("a document with several open cases is asked about, never guessed (§26.6.3)",
          "which one" in linked.lower(), linked[:240])
    check("the choice lists the customer's own references",
          "VP-" in linked, linked[:240])

    linked = say("1")
    check("a linked customer's photo earns an upload link (§26.6.3, WA-38)",
          "/wa/upload/" in linked, linked[:240])
    check("the upload answer still states the evidence rule",
          "verification file" in linked, linked[:240])

    if "/wa/upload/" in linked:
        token = linked.split("/wa/upload/")[1].split()[0].strip()
        holder = client()
        redeemed = holder.post(f"/public/wa/handoff/upload/{token}/redeem")
        check("the upload link opens the customer's own case (§26.5)",
              redeemed.status_code == 200, f"http {redeemed.status_code}: {redeemed.text[:160]}")
        replay = client().post(f"/public/wa/handoff/upload/{token}/redeem")
        check("a spent upload link is dead, like every other handoff link (§26.5)",
              replay.status_code == 404, f"http {replay.status_code}")

    # Leave the customer unlinked, as `_run_linking_checks` does: the 1:1 rule means a
    # stray link would refuse whatever a later stage tries to claim.
    customer.delete("/channel/whatsapp/link/me")


def _link_number(ctx: Ctx, phone: str, customer=None) -> bool:
    """Link *phone* to a customer (the stage's own by default) so case-scoped flows run."""
    customer = customer if customer is not None else ctx.customer
    started = customer.post("/channel/whatsapp/link/me/start", json={"phoneE164": f"+{phone}"})
    if started.status_code != 200:
        warn("could not link the media number",
             f"start http {started.status_code}: {started.text[:160]}")
        return False
    confirmed = customer.post("/channel/whatsapp/link/me/confirm",
                              json={"phoneE164": f"+{phone}", "code": TEST_OTP})
    if confirmed.status_code != 200:
        warn("could not link the media number",
             f"confirm http {confirmed.status_code}: {confirmed.text[:160]}")
        return False
    return True


def _run_intake_checks(ctx: Ctx) -> None:
    """Chat intake through to a seeded draft (§5.1, D69/D70/D71).

    The property only a live stack can show: four answers given over the webhook come back
    out of the website as a **real draft row**, filled with the wizard's own payload shape.
    A renamed key or a lost answer is invisible to unit tests on either side of the seam —
    each one passes happily against its own idea of the shape.
    """
    root, customer = ctx.root, ctx.customer
    phone = f"23480{uuid.uuid4().int % 10**8:08d}"

    def say(text: str) -> str:
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        root.post("/dev/whatsapp/inbound", json={"fromPhone": phone, "text": text}).raise_for_status()
        messages = root.get("/dev/whatsapp/outbox").json()["data"].get("messages", [])
        mine = [m for m in messages if phone[-10:] in str(m.get("to", ""))]
        return str(mine[0].get("text", "")) if mine else ""

    say("Hi")  # §26.6.1 welcome, which answers the turn on its own
    opening = say("I want to verify a property")
    check("a stranger can start an intake with no account (§26.3.4, D69)",
          "what are you verifying" in opening.lower(), opening[:120])

    location_prompt = say("1")
    check("the intake asks where the property is (§5.1)",
          "where is the" in location_prompt.lower(), location_prompt[:120])

    state_prompt = say("12 Ademola Street, Ikeja")
    check("the intake asks for the state", "state" in state_prompt.lower(), state_prompt[:120])

    tier_prompt = say("Lagos")
    check("the tier prompt quotes live prices (D54)", "₦" in tier_prompt, tier_prompt[:160])

    handoff = say("2")
    check("completing the intake hands off with a single-use link (§26.5)",
          "/wa/intake/" in handoff, handoff[:200])
    check("the handoff repeats the payment pledge (§26.1.1)",
          "veriprops.ng" in handoff and "address bar" in handoff, handoff[:200])

    token = handoff.split("/wa/intake/")[1].split()[0].strip()

    # The landing is authenticated (D69): the token carries a conversation, the session
    # says whose draft it becomes.
    unauthenticated = client()
    refused = unauthenticated.post(f"/wa/intake/{token}/redeem")
    check("the intake landing refuses an anonymous caller (D69)",
          refused.status_code in (401, 403), f"http {refused.status_code}")

    redeemed = customer.post(f"/wa/intake/{token}/redeem")
    check("a signed-in customer redeems the intake link (§26.5)",
          redeemed.status_code == 200, f"http {redeemed.status_code}: {redeemed.text[:160]}")
    if redeemed.status_code != 200:
        return

    verification_id = redeemed.json()["data"]["verificationId"]
    check("redemption returns the draft to open", bool(verification_id))

    # The whole point of D69/D70: the answers are in the row the web wizard reads — and
    # this is the exact endpoint it resumes from, `/draft`, not the detail DTO (which
    # carries `draftStep` but deliberately not the payload).
    draft = customer.get(f"/verifications/{verification_id}/draft").json()["data"]
    payload = draft.get("payload") or {}
    check("the seeded draft opens on the property step, with the chat's answers filled in",
          draft.get("step") == 0, f"step={draft.get('step')}")
    check("the chat's answers land in the draft the wizard reads (D69)",
          payload.get("property", {}).get("address") == "12 Ademola Street, Ikeja",
          f"payload={payload}")
    check("the tier the customer chose in chat survives the handoff",
          payload.get("tier") == "STANDARD", f"tier={payload.get('tier')}")
    check("the state the customer gave in chat survives the handoff",
          payload.get("property", {}).get("state") == "Lagos")
    check("consent is never taken in chat (§5.3)",
          payload.get("consentAccepted") is False)

    # Single-use, like every other §26.5 link.
    replay = customer.post(f"/wa/intake/{token}/redeem")
    check("a spent intake link is dead (§26.5)",
          replay.status_code == 404, f"http {replay.status_code}")


def _create_payable_case(ctx: Ctx, customer=None) -> str:
    """A SUBMITTED verification for a customer — the state a pay link targets."""
    customer = customer if customer is not None else ctx.customer
    r = customer.post("/verifications/draft", headers={"Idempotency-Key": idem_key()})
    if r.status_code != 200:
        check("created a payable case for the WhatsApp handoff", False,
              f"draft http {r.status_code}: {r.text[:160]}")
        return ""
    case_id = r.json()["data"]["id"]

    r = customer.post(f"/verifications/{case_id}/submit", json={
        "property": {
            "property_type": "LAND", "address": "12 Admiralty Way, Lekki Phase 1",
            "state": "Lagos", "lga": "Eti-Osa", "landmark": "Near the toll gate",
        },
        "tier": "BASIC", "currency": "NGN",
        "consent": {"consent_version": consent_version_for("VERIFICATION_TERMS")},
    })
    check("created a payable case for the WhatsApp handoff", r.status_code == 200,
          f"submit http {r.status_code}: {r.text[:200]}")
    return case_id if r.status_code == 200 else ""


def _run_consent_checks(ctx: Ctx) -> str:
    """§26.4.6's two opt-ins and D64's keywords, over the real surfaces (WA-27).

    Returns the linked number, so the milestone stage can keep using it.

    What only a live stack shows here is the *shape of the answer*: STOP has to be honoured
    by the bot in one turn, from the customer's literal word, with the ledger actually
    written — a unit test can prove the service method was called, but not that the word
    reached it through the keyword table, the classifier bypass and the transaction.
    """
    root, customer = ctx.root, ctx.customer
    phone = f"23480{uuid.uuid4().int % 10**8:08d}"

    def say(text: str) -> str:
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        root.post("/dev/whatsapp/inbound",
                  json={"fromPhone": phone, "text": text}).raise_for_status()
        replies = _outbound_to(ctx, phone)
        return str(replies[0].get("text", "")) if replies else ""

    def consents() -> dict:
        return customer.get("/channel/whatsapp/consent/me").json()["data"]

    # Both unticked before anyone is asked — §26.4.6's required default, and the one place
    # where "no record" must not be read as anything else.
    initial = consents()
    check("a customer who has never been asked has consented to nothing (§26.4.6)",
          initial.get("utility") is False and initial.get("marketing") is False,
          f"consents={initial}")

    # The pay screen's capture point.
    saved = customer.put("/channel/whatsapp/consent/me?source=PAY_SCREEN",
                         json={"utility": True, "marketing": True})
    check("the payment step records both opt-ins (§26.4.6)",
          saved.status_code == 200 and saved.json()["data"]["utility"] is True,
          f"http {saved.status_code}: {saved.text[:160]}")

    # The landing's grant-scoped twin refuses a caller holding no grant — the same
    # not-found posture as every other handoff endpoint (D76, §26.5).
    ungranted = client().put("/public/wa/handoff/pay/consent",
                             json={"utility": True, "marketing": True})
    check("the landing's consent endpoint refuses a caller with no grant (D76)",
          ungranted.status_code == 404, f"http {ungranted.status_code}")

    if not _link_number(ctx, phone):
        return ""

    # A fresh number: let §26.6.1's welcome have its turn before the keywords are tested.
    say("Hi")

    stopped = say("STOP")
    check("STOP is answered by the bot in one turn, never routed to a person (D64)",
          "stopped" in stopped.lower(), stopped[:200])
    after_stop = consents()
    check("STOP revokes both consents — the customer said stop, not stop some (D64)",
          after_stop.get("utility") is False and after_stop.get("marketing") is False,
          f"consents={after_stop}")

    started = say("START")
    after_start = consents()
    check("START restores progress updates (D64)",
          after_start.get("utility") is True, f"consents={after_start}")
    check("START leaves marketing off — re-consent is a deliberate act on the web (D64)",
          after_start.get("marketing") is False, f"consents={after_start}")
    check("the reply says so, so the customer is not left assuming otherwise",
          "offers" in started.lower(), started[:200])

    return phone


def _run_milestone_checks(ctx: Ctx, phone: str) -> None:
    """§26.6.2 milestones and §26.7 report delivery, driven by real state (WA-34/WA-35).

    Every assertion here needs the whole stack standing up at once — a domain event, the
    rule table, the D63 consent ledger, the linked-number lookup and Meta's template shape
    — which is exactly the seam four stacked faults hid behind the last time this channel
    shipped an outbound path that was quietly dead.

    The negative half matters as much as the positive: a customer who revokes consent must
    stop receiving WhatsApp and **keep** receiving email (WA-35).
    """
    if not phone:
        warn("WhatsApp milestone checks skipped", "the consent stage could not link a number")
        return
    root, admin, customer = ctx.root, ctx.admin, ctx.customer

    def outbound_names() -> list:
        return [m.get("templateName") for m in _outbound_to(ctx, phone)]

    def templates_to(name: str) -> list:
        return [m for m in _outbound_to(ctx, phone) if m.get("templateName") == name]

    # Consent on for the positive half. START above restored utility, which is the gate
    # that matters, but set both explicitly so this stage does not depend on that order.
    customer.put("/channel/whatsapp/consent/me?source=ACCOUNT_SETTINGS",
                 json={"utility": True, "marketing": True}).raise_for_status()

    case_id = _create_standard_case(ctx)
    if not case_id:
        return
    vid = customer.get(f"/verifications/{case_id}").json()["data"]["vid"]

    # ── payment_confirmed ────────────────────────────────────────────────────
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    payment = customer.post(f"/payments/initiate/{case_id}", json={"method": "CARD"},
                            headers={"Idempotency-Key": idem_key()}).json()["data"]
    stub_pay(customer, payment["checkoutUrl"])

    confirmed = templates_to("payment_confirmed")
    check("payment confirmation reaches the consented customer as a §26.7 template (WA-34)",
          bool(confirmed), f"templates={outbound_names()}")
    if confirmed:
        check("the case reference is Meta's first positional body parameter",
              confirmed[0].get("templateVariables", {}).get("1") == vid,
              f"variables={confirmed[0].get('templateVariables')}")

    # ── verification_started ─────────────────────────────────────────────────
    roles = list(ctx.seed["tasks"].keys())
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    _drive_tasks_to_submitted(ctx, case_id, roles)
    check("work starting announces itself as its own milestone (D66, WA-34)",
          bool(templates_to("verification_started")), f"templates={outbound_names()}")

    # ── inspection_complete ──────────────────────────────────────────────────
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    admin.post(f"/admin/review/{case_id}/tasks/FIELD/approve",
               json={"quality": 92}).raise_for_status()
    check("approving the field task announces the inspection (D66, WA-34)",
          bool(templates_to("inspection_complete")), f"templates={outbound_names()}")

    root.delete("/dev/whatsapp/outbox").raise_for_status()
    admin.post(f"/admin/review/{case_id}/tasks/REGISTRY/approve",
               json={"quality": 90}).raise_for_status()
    check("approving another role announces no inspection — only FIELD is the inspection",
          not templates_to("inspection_complete"), f"templates={outbound_names()}")

    # ── report_ready (§26.7, D75) ─────────────────────────────────────────────
    for role in roles:
        if role not in ("FIELD", "REGISTRY"):
            admin.post(f"/admin/review/{case_id}/tasks/{role}/approve",
                       json={"quality": 90}).raise_for_status()
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    released = admin.post(f"/admin/review/{case_id}/release",
                          json={"reason": "All checks passed."})
    check("the milestone case released", released.status_code == 200,
          f"http {released.status_code}: {released.text[:200]}")

    ready = templates_to("report_ready")
    check("report-ready reaches the consented customer on WhatsApp (WA-35)",
          bool(ready), f"templates={outbound_names()}")
    if ready:
        link = ready[0].get("templateVariables", {}).get("2", "")
        check("the report link is the portal deep link, not a 15-minute token (D75)",
              "/portal/verifications/" in link and "/wa/report/" not in link,
              f"link={link}")
        check("the link names the customer's own case", vid in link, f"link={link}")

    # ── The negative half: consent revoked, email unaffected (WA-35) ──────────
    root.post("/dev/whatsapp/inbound",
              json={"fromPhone": phone, "text": "STOP"}).raise_for_status()
    revoked = customer.get("/channel/whatsapp/consent/me").json()["data"]
    check("the customer is opted out again for the negative half",
          revoked.get("utility") is False, f"consents={revoked}")

    second = _create_standard_case(ctx)
    if not second:
        return
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    payment = customer.post(f"/payments/initiate/{second}", json={"method": "CARD"},
                            headers={"Idempotency-Key": idem_key()}).json()["data"]
    stub_pay(customer, payment["checkoutUrl"])

    check("an opted-out customer receives no WhatsApp milestone (WA-16/WA-27)",
          not templates_to("payment_confirmed"), f"templates={outbound_names()}")

    delivered = root.get(f"/dev/messages/latest?recipient={ctx.customer_email}").json()["data"]
    check("their email still arrives — the durable record never depends on a messaging "
          "preference (WA-35)",
          delivered.get("found") is True, f"latest={delivered}")


def _create_standard_case(ctx: Ctx) -> str:
    """A STANDARD-tier submitted case, so its task set matches the seeded agents' roles."""
    customer = ctx.customer
    r = customer.post("/verifications/draft", headers={"Idempotency-Key": idem_key()})
    if r.status_code != 200:
        check("created a case for the milestone checks", False,
              f"draft http {r.status_code}: {r.text[:160]}")
        return ""
    case_id = r.json()["data"]["id"]
    r = customer.post(f"/verifications/{case_id}/submit", json={
        "property": {
            "property_type": "LAND", "address": "9 Bourdillon Road, Ikoyi",
            "state": "Lagos", "lga": "Eti-Osa", "landmark": "Near the roundabout",
        },
        "tier": "STANDARD", "currency": "NGN",
        "consent": {"consent_version": consent_version_for("VERIFICATION_TERMS")},
    })
    check("created a case for the milestone checks", r.status_code == 200,
          f"submit http {r.status_code}: {r.text[:200]}")
    return case_id if r.status_code == 200 else ""


def _drive_tasks_to_submitted(ctx: Ctx, case_id: str, roles: list) -> None:
    """Assign, accept, start and submit every role, so the case derives to UNDER_REVIEW.

    A condensed replay of `stage_execution` against a second case — the milestones need
    real transitions, and a status forced from the outside would prove nothing about the
    events those transitions publish.
    """
    admin = ctx.admin
    for role in roles:
        admin.post(f"/admin/verifications/{case_id}/tasks/{role}/assign",
                   json={"agentId": ctx.seed["agents"][role]}).raise_for_status()
        agent = ctx.agent(role)
        tasks = agent.get("/agents/tasks").json()["data"]["items"]
        mine = next((t for t in tasks if t["verificationId"] == case_id), None)
        if mine is None:
            check(f"the {role} agent was assigned the milestone case", False)
            continue
        agent.post(f"/agents/tasks/{mine['id']}/accept").raise_for_status()
        agent.post(f"/agents/tasks/{mine['id']}/start").raise_for_status()
        agent.post(
            f"/agents/tasks/{mine['id']}/evidence",
            files={"file": (f"{role.lower()}-site.png", MINIMAL_PNG, "image/png")},
            data={"kind": "PHOTO", "gps_latitude": "6.4478", "gps_longitude": "3.4723"},
        ).raise_for_status()
        agent.post(f"/agents/tasks/{mine['id']}/submit",
                   json={"payload": _ROLE_PAYLOADS[role]}).raise_for_status()


def _run_delegate_checks(ctx: Ctx) -> None:
    """§26.4.5's slim delegate, end to end (Decision O, D67/D77; WA-26).

    The properties that only a live stack can show, and that matter most because this is
    access control:

    * a delegate's number resolves through a **second** lookup, so the bot answers them
      about their one case without `whatsapp_links` ever knowing them;
    * what they are answered carries no report link and no upload link — asserted against
      the real reply, not against a template's declaration;
    * a stranger with the same question gets nothing at all; and
    * revocation is effective on the very next milestone, because the audience is resolved
      at send time.
    """
    root, customer = ctx.root, ctx.customer
    delegate_phone = f"23480{uuid.uuid4().int % 10**8:08d}"
    stranger_phone = f"23480{uuid.uuid4().int % 10**8:08d}"

    def say(phone: str, text: str) -> str:
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        root.post("/dev/whatsapp/inbound",
                  json={"fromPhone": phone, "text": text}).raise_for_status()
        replies = _outbound_to(ctx, phone)
        return str(replies[0].get("text", "")) if replies else ""

    def templates_to(phone: str, name: str) -> list:
        return [m for m in _outbound_to(ctx, phone) if m.get("templateName") == name]

    case_id = _create_standard_case(ctx)
    if not case_id:
        return
    vid = customer.get(f"/verifications/{case_id}").json()["data"]["vid"]

    # Nobody is authorized yet.
    listed = customer.get(f"/verifications/{case_id}/delegates").json()["data"]
    check("a case starts with no delegate (§26.4.5)", listed == [], f"delegates={listed}")

    # The buyer nominates someone. Nothing is visible yet — the row exists to hold the
    # one-per-case slot, and the OTP is what turns it into a grant.
    authorized = customer.post(f"/verifications/{case_id}/delegates",
                               json={"name": "Tunde", "phoneE164": f"+{delegate_phone}"})
    check("the buyer can authorize a delegate from their own case (§26.4.5)",
          authorized.status_code == 200,
          f"http {authorized.status_code}: {authorized.text[:200]}")

    pending = customer.get(f"/verifications/{case_id}/delegates").json()["data"]
    check("an unconfirmed delegate is listed but not yet verified",
          len(pending) == 1 and pending[0]["verified"] is False, f"delegates={pending}")

    # The welcome answers a fresh number's first turn (§26.6.1), so get it out of the way —
    # otherwise this assertion passes on a greeting rather than on the refusal it means to
    # test.
    say(delegate_phone, "Hi")
    unverified_reply = say(delegate_phone, "what's the status")
    # The refusal (D79) names the delegate route as one of two ways forward, so its *words*
    # legitimately contain "as a delegate". What must be absent is the case and the
    # delegate greeting — the two things that would mean the grant had taken effect early.
    check("an unverified delegate is told nothing about the case (§26.4.3)",
          vid not in unverified_reply
          and "you're receiving updates on" not in unverified_reply,
          unverified_reply[:200])

    # A second nomination while one is live is refused — two codes in flight to two
    # numbers is worse than a clear answer.
    second = customer.post(f"/verifications/{case_id}/delegates",
                           json={"name": "Bola", "phoneE164": f"+{stranger_phone}"})
    check("a case takes only one delegate at a time (§26.4.5)",
          second.status_code >= 400, f"http {second.status_code}")

    confirmed = customer.post(f"/verifications/{case_id}/delegates/confirm",
                              json={"code": TEST_OTP})
    check("the delegate's number is OTP-verified before anything is shared (§26.4.5)",
          confirmed.status_code == 200,
          f"http {confirmed.status_code}: {confirmed.text[:200]}")

    # The bot's second identity lookup: this number has no account, and still gets an
    # answer — about exactly one case.
    delegate_reply = say(delegate_phone, "what's the status")
    check("a verified delegate is answered about their case (WA-26)",
          vid in delegate_reply, delegate_reply[:240])
    check("the bot names their role, so they know what they are (§26.4.5)",
          "delegate" in delegate_reply.lower(), delegate_reply[:240])
    check("a delegate is never handed a report or upload link (§26.4.5)",
          "/wa/" not in delegate_reply and "http" not in delegate_reply,
          delegate_reply[:240])
    check("a delegate is not invited to sign in — they have no account to sign into",
          "sign in" not in delegate_reply.lower(), delegate_reply[:240])

    # The social-engineering script §26.4.5 exists to defeat. A fresh number, so §26.6.1's
    # welcome has to have its turn before the question being tested gets answered.
    say(stranger_phone, "Hi")
    stranger_reply = say(stranger_phone, "what's the status of my brother's verification")
    check("a stranger asking about a case is told nothing about it (§26.4.5)",
          vid not in stranger_reply, stranger_reply[:240])
    check("and is pointed at the legitimate routes rather than stonewalled",
          "delegate" in stranger_reply.lower(), stranger_reply[:240])

    # A milestone reaches the delegate as `delegate_status`, never as the customer's
    # template — which is what makes "status only" structural.
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    payment = customer.post(f"/payments/initiate/{case_id}", json={"method": "CARD"},
                            headers={"Idempotency-Key": idem_key()}).json()["data"]
    stub_pay(customer, payment["checkoutUrl"])

    delegate_templates = templates_to(delegate_phone, "delegate_status")
    check("a milestone reaches the delegate as the §26.7 delegate template (WA-26)",
          bool(delegate_templates),
          f"templates={[m.get('templateName') for m in _outbound_to(ctx, delegate_phone)]}")
    if delegate_templates:
        variables = delegate_templates[0].get("templateVariables", {})
        check("the delegate template carries the case reference and a status label",
              variables.get("1") == vid and bool(variables.get("2")),
              f"variables={variables}")
    check("a delegate never receives the customer's own milestone template",
          not templates_to(delegate_phone, "payment_confirmed"),
          f"templates={[m.get('templateName') for m in _outbound_to(ctx, delegate_phone)]}")

    # D77: STOP from a delegate ends the delegation, because they have no consent row.
    stopped = say(delegate_phone, "STOP")
    check("STOP from a delegate is acknowledged by the bot (D77)",
          bool(stopped) and "won't receive" in stopped, stopped[:200])
    after_stop = customer.get(f"/verifications/{case_id}/delegates").json()["data"]
    check("STOP ends the delegation itself — the only lever a non-user has (D77)",
          after_stop == [], f"delegates={after_stop}")

    notifications = customer.get("/notifications?page=0&page_size=50").json()["data"]["items"]
    check("the account holder is told their delegate opted out (D77)",
          any(n.get("type") == "DELEGATE_REVOKED" for n in notifications),
          f"types={sorted({n.get('type') for n in notifications})}")

    # Revocation is effective immediately on the read path, because the audience is
    # resolved at lookup time rather than stored on anything: the number that was a
    # delegate a moment ago now gets the stranger's answer.
    revoked_reply = say(delegate_phone, "what's the status")
    check("a revoked delegate immediately stops resolving as one (§26.4.5)",
          vid not in revoked_reply
          and "you're receiving updates on" not in revoked_reply,
          revoked_reply[:200])

    # And the slot is free again, which a plain unique constraint would have prevented.
    replacement = customer.post(f"/verifications/{case_id}/delegates",
                                json={"name": "Bola", "phoneE164": f"+{stranger_phone}"})
    check("a revoked delegate does not block a replacement (§26.4.5)",
          replacement.status_code == 200,
          f"http {replacement.status_code}: {replacement.text[:200]}")


def _run_pay_report_handoff_checks(ctx: Ctx) -> None:
    """§26.3.4's pay and report handoffs, asked for in words (WA-17, §26.4.2).

    Only a live stack proves this one, and the gap it closes was invisible to unit tests
    precisely because every piece existed and passed on its own: the capability matrix
    declared `PAY` and `VIEW_REPORT` as `HANDOFF`, `handoff_intent_for` returned the right
    intent, the token service minted, and the landings rendered — but no intent reached any
    of it, so both links were unreachable from an actual conversation. What is asserted
    here is the whole path: a customer's words, through the classifier, to a link that opens.

    The eligibility rule is the other thing worth driving for real. A report link is offered
    only once the report has passed the §8 release gate, and the difference between
    `UNDER_REVIEW` and `COMPLETED` is a projection detail no unit test of the bot can see.
    """
    root, customer = ctx.root, ctx.customer
    phone = f"23480{uuid.uuid4().int % 10**8:08d}"

    def say(text: str) -> str:
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        root.post("/dev/whatsapp/inbound",
                  json={"fromPhone": phone, "text": text}).raise_for_status()
        replies = _outbound_to(ctx, phone)
        return str(replies[0].get("text", "")) if replies else ""

    # An unlinked number asking to pay gets no link — the §26.4.3 rule, on the surface
    # where breaking it would cost someone money rather than privacy.
    say("Hi")
    unlinked = say("how do I pay?")
    check("an unlinked number is never handed a payment link (§26.4.3)",
          "/wa/pay/" not in unlinked, unlinked[:200])
    check("...and is told how to link rather than left with nothing",
          "link my account" in unlinked.lower(), unlinked[:200])

    if not _link_number(ctx, phone):
        return

    case_id = _create_payable_case(ctx)
    if not case_id:
        return

    pay_reply = say("I want to pay")
    check("a linked customer with an unpaid case gets a pay link (§26.3.4, WA-17)",
          "/wa/pay/" in pay_reply, pay_reply[:240])
    # §26.1.1 — the pledge rides every payment handoff, and this is the message an
    # impersonator would imitate most precisely.
    check("the pay handoff carries the §26.1.1 payment pledge",
          "veriprops.ng" in pay_reply, pay_reply[:240])

    token = pay_reply.split("/wa/pay/")[1].split()[0].strip() if "/wa/pay/" in pay_reply else ""
    redeemed = client().post(f"/public/wa/handoff/pay/{token}/redeem") if token else None
    check("the pay link the bot minted actually opens its landing (§26.4.2)",
          redeemed is not None and redeemed.status_code == 200,
          f"http {redeemed.status_code if redeemed is not None else 'no token'}: "
          f"{redeemed.text[:200] if redeemed is not None else pay_reply[:200]}")

    # The report half. This customer already owns the stage's delivered case (released
    # back in `stage_report`), so the interesting assertion is not "no link yet" — it is
    # that the link goes to the *delivered* case and never to the unpaid one just created.
    # A report token minted for a case with no released report is what the §8 gate exists
    # to prevent, and it would be indistinguishable from a working link until it opened.
    delivered = customer.get(f"/verifications/{ctx.vid_id}").json()["data"]
    if delivered.get("status") != "COMPLETED":
        warn("report handoff not exercised against a delivered case",
             f"the stage's first case is {delivered.get('status')}, not COMPLETED")
        return

    report_reply = say("send me my report")
    check("a delivered case earns a report link on request (§26.4.2)",
          "/wa/report/" in report_reply, report_reply[:240])
    # One link, not a "which one?" — the unpaid case has no report, so it must not be on
    # the list. If eligibility leaked, the bot would ask the customer to choose between a
    # delivered report and a case that has none.
    check("the unpaid case is not offered as a report (§8 release gate)",
          "Which one" not in report_reply and "which one" not in report_reply,
          report_reply[:240])


def _run_channel_analytics_checks(ctx: Ctx) -> None:
    """§26.10's seven metrics, against traffic this stage actually generated (WA-43).

    Why this belongs in the drive-through rather than only in unit tests: a metric is
    worthless if it does not *move*. Every count here has a recorder call somewhere in the
    conversation path, and each of those is a best-effort side write that fails silently by
    design (D80) — so a broken call site produces a dashboard of zeros and no error
    anywhere. Reading the numbers back after driving real conversations is the only thing
    that catches it.
    """
    admin = ctx.admin

    panel = admin.get("/admin/analytics/whatsapp")
    check("the §26.10 channel analytics endpoint answers for an admin (WA-43)",
          panel.status_code == 200, f"http {panel.status_code}: {panel.text[:200]}")
    if panel.status_code != 200:
        return
    data = panel.json()["data"]

    check("the window every figure covers is stated (§26.10)",
          isinstance(data.get("windowDays"), int) and data["windowDays"] > 0,
          f"windowDays={data.get('windowDays')}")

    # Enquiries: every number this stage spoke to opened a conversation.
    check("conversations this stage drove were counted as enquiries",
          data.get("enquiries", 0) > 0, f"enquiries={data.get('enquiries')}")

    # Escalations: the media checks sent a voice note, which §26.6.3 routes to a person
    # under its own reason — so both the count and the breakdown must be non-empty.
    reasons = {row["label"]: row["count"] for row in data.get("escalationsByReason", [])}
    check("escalations were counted with their §26.10 reasons",
          data.get("escalations", 0) > 0 and bool(reasons), f"reasons={reasons}")
    check("a voice note is counted under its own reason, not lumped with other media",
          "VOICE_NOTE" in reasons, f"reasons={reasons}")

    # Voice-note volume comes off the inbound journal, not the escalation reason: a voice
    # note arriving on a thread already in HUMAN mode never reaches the bot.
    check("voice-note volume is counted (§26.10, v1.1 trigger data)",
          data.get("voiceNotes", 0) > 0, f"voiceNotes={data.get('voiceNotes')}")

    # The seam: `_run_intake_checks` ran a chat intake through to a seeded draft.
    check("a completed chat intake was counted (§26.10 seam denominator)",
          data.get("intakeStarted", 0) > 0 and data.get("intakeCompleted", 0) > 0,
          f"started={data.get('intakeStarted')} completed={data.get('intakeCompleted')}")

    # Consent: `_run_consent_checks` left one number opted into utility only.
    check("linked numbers are the opt-in denominator (D84)",
          data.get("linkedNumbers", 0) > 0, f"linked={data.get('linkedNumbers')}")
    check("the utility opt-in rate is derived, not stored",
          0.0 <= float(data.get("utilityOptInRate", -1)) <= 1.0,
          f"rate={data.get('utilityOptInRate')}")

    # Attribution: page codes appear only when a customer arrives through the widget, and
    # nothing above does — so `direct` is the honest expectation, and its presence proves
    # unattributed demand is counted rather than dropped.
    codes = {row["label"] for row in data.get("enquiriesByPageCode", [])}
    check("enquiries with no widget marker are still counted, under `direct` (§26.10)",
          "direct" in codes, f"codes={sorted(codes)}")

    # The §26.4.1 marker, read back out of a real inbound message (D85).
    marked_phone = f"23480{uuid.uuid4().int % 10**8:08d}"
    ctx.root.post("/dev/whatsapp/inbound", json={
        "fromPhone": marked_phone, "text": "Hi Veriprops! [ref: web-pricing]",
    }).raise_for_status()
    attributed = admin.get("/admin/analytics/whatsapp").json()["data"]
    marked = {row["label"]: row["count"] for row in attributed.get("enquiriesByPageCode", [])}
    check("a widget page code is read off the customer's first message (§26.4.1, D85)",
          marked.get("web-pricing", 0) > 0, f"codes={marked}")
    # ...and stripped, so the classifier and the console see what the customer wrote.
    welcomed = _outbound_to(ctx, marked_phone)
    check("the marker never appears in what the bot says back (D85)",
          all("[ref:" not in str(m.get("text", "")) for m in welcomed),
          f"replies={[str(m.get('text'))[:60] for m in welcomed]}")

    # Meta's verdict on the number — synced through the stub, which never reaches Meta.
    synced = admin.post("/admin/analytics/whatsapp/quality/sync")
    check("the Meta quality rating syncs into the registry (§26.10, D81)",
          synced.status_code == 200, f"http {synced.status_code}: {synced.text[:200]}")
    if synced.status_code == 200:
        health = synced.json()["data"].get("numberHealth") or {}
        check("...and comes back with the timestamp that dates it",
              health.get("qualityRating") in {"GREEN", "YELLOW", "RED", "UNKNOWN"}
              and bool(health.get("syncedAt")),
              f"health={health}")

    # RBAC: analytics is VIEW_ANALYTICS-gated, so a customer must get nowhere near it.
    forbidden = ctx.customer.get("/admin/analytics/whatsapp")
    check("a customer cannot read the channel analytics",
          forbidden.status_code in (401, 403), f"http {forbidden.status_code}")


def _run_failure_drill_checks(ctx: Ctx) -> None:
    """§26.6.5's fallback, drilled rather than asserted (§26.11 launch gate, WA-40).

    The launch checklist says "failure fallback tested (kill the bot, observe the auto-reply
    + alert)", and until now that line was carried by unit tests raising inside a mock. What
    those cannot show is that a **real** failure in a running process reaches the warm
    handover at all, rather than becoming a 500 in the webhook, a Meta retry, a throttle,
    and a customer left with silence — which is the exact outcome §26.6.5 exists to rule out.

    So one real turn is made to fail, through `POST /dev/whatsapp/fail-next-turn`, and both
    halves of the promise are checked: the customer gets an apology and a person, and an
    admin gets told. The fault is one-shot, so the turn after it must be answered normally —
    a drill that left the number silenced would be worse than no drill.
    """
    root, admin = ctx.root, ctx.admin
    phone = f"23480{uuid.uuid4().int % 10**8:08d}"

    def say(text: str) -> str:
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        root.post("/dev/whatsapp/inbound",
                  json={"fromPhone": phone, "text": text}).raise_for_status()
        replies = _outbound_to(ctx, phone)
        return str(replies[0].get("text", "")) if replies else ""

    # Get the §26.6.1 welcome out of the way, so the failing turn is an ordinary one.
    say("Hi")

    before = admin.get("/notifications?page=0&page_size=1").json()["data"]["meta"]["total"]

    armed = root.post("/dev/whatsapp/fail-next-turn")
    check("the failure drill can be armed outside production (§26.11)",
          armed.status_code == 200, f"http {armed.status_code}: {armed.text[:160]}")

    failed_turn = say("how much for a Lagos land check?")
    check("a failing bot turn still answers the customer (§26.6.5, WA-40)",
          bool(failed_turn), "the customer got nothing back")
    check("...with an apology and a person, not an error",
          "technical" in failed_turn.lower(), failed_turn[:200])
    # The promise has to be concrete, and Decision G gives it two shapes: inside staffed
    # hours a person is joining now, outside them a stated number of hours. Asserting only
    # the window would fail every run made during business hours — and "joining now" is the
    # stronger of the two promises, not a weaker one.
    check("...and a concrete human promise, in whichever shape Decision G's coverage gives",
          "team member" in failed_turn.lower(), failed_turn[:200])

    after = admin.get("/notifications?page=0&page_size=1").json()["data"]["meta"]["total"]
    check("an admin is alerted that the bot pipeline failed (§26.6.5)",
          after > before, f"notifications {before} -> {after}")

    # One-shot: the next message is answered normally. Without this the drill could leave
    # an environment quietly broken, and nobody would run it twice.
    recovered = say("how much for a Lagos land check?")
    check("the fault is one-shot — the next turn is answered normally",
          "technical" not in recovered.lower() and bool(recovered), recovered[:200])

    # §26.10 counts it: a spike in PIPELINE_FAILURE is the operational signal that the
    # channel is degraded, and it is the reason the escalation reasons are broken out.
    reasons = {
        row["label"]: row["count"]
        for row in admin.get("/admin/analytics/whatsapp").json()["data"]["escalationsByReason"]
    }
    check("the failure is counted under PIPELINE_FAILURE (§26.10)",
          reasons.get("PIPELINE_FAILURE", 0) > 0, f"reasons={reasons}")


def _run_channel_erasure_checks(ctx: Ctx) -> None:
    """§26.8 compliance on a live stack: the consent ledger exports, and erasure reaches
    the channel (WA-42).

    Both halves shipped with unit tests and neither had ever been driven end to end, which
    is the wrong way round for the two claims a regulator actually asks us to demonstrate.
    A mock proves `PiiPseudonymiser` issues the UPDATEs; it cannot prove those UPDATEs reach
    the rows the *bot* reads on the next message — and the channel keys on a phone number
    rather than a user id, so "erased" and "still answers as a linked customer" are entirely
    capable of being true at the same time.

    Runs last in the stage, after `_run_channel_analytics_checks`: erasure revokes a link
    and drops a bot session, which would move §26.10's numbers out from under the assertions
    that read them.

    The subject is a purpose-made account rather than the stage's customer, whose case,
    delegate and linked number the checks above still depend on.
    """
    root, admin = ctx.root, ctx.admin
    phone = f"23480{uuid.uuid4().int % 10**8:08d}"

    subject, subject_email = signup_fresh_user("wa-erasable", first_name="Nkem", last_name="Obi")

    def say(text: str) -> str:
        root.delete("/dev/whatsapp/outbox").raise_for_status()
        root.post("/dev/whatsapp/inbound",
                  json={"fromPhone": phone, "text": text}).raise_for_status()
        replies = _outbound_to(ctx, phone)
        return str(replies[0].get("text", "")) if replies else ""

    def pack_for(case_id: str) -> str:
        return admin.get(f"/admin/audit/verifications/{case_id}/export").text

    case_id = _create_payable_case(ctx, customer=subject)
    if not case_id:
        return

    # ── §19.3: the consent ledger, before anyone is asked ─────────────────────────
    # Absence must read as absence. A pack that emitted "utility: false" for a customer
    # nobody ever asked would be asserting an event that never happened — which is exactly
    # the claim a dispute would turn on.
    check("a customer never asked contributes no consent row to the pack (§26.8)",
          "WHATSAPP_CONSENT" not in pack_for(case_id))

    granted = subject.put("/channel/whatsapp/consent/me?source=PAY_SCREEN",
                          json={"utility": True, "marketing": False})
    check("the erasure subject's utility opt-in is recorded (§26.4.6)",
          granted.status_code == 200, f"http {granted.status_code}: {granted.text[:160]}")

    # Both controls are written on every save (they are always shown together, so an
    # untouched one must not be indistinguishable from one that was never rendered), which
    # is why declining marketing produces a REVOKED row rather than no row: the customer
    # was asked and said no, and §26.8 wants that answer timestamped too.
    pack = pack_for(case_id)
    consent_lines = [ln for ln in pack.splitlines() if ln.startswith("WHATSAPP_CONSENT")]
    check("the §26.4.6 consent ledger exports in the §19.3 audit pack (WA-42)",
          len(consent_lines) == 2, f"rows={len(consent_lines)}")
    utility = next((ln for ln in consent_lines if "UTILITY" in ln), "")
    marketing = next((ln for ln in consent_lines if "MARKETING" in ln), "")
    check("...the opt-in that was given reads GRANTED", "GRANTED" in utility, utility[:200])
    check("...the one that was declined reads REVOKED, not absent",
          "REVOKED" in marketing, marketing[:200])
    check("...each carrying the timestamp pair that *is* the record, and its capture point",
          "granted_at=" in utility and "PAY_SCREEN" in utility, utility[:200])

    # ── Give the erasure something to find across the channel ─────────────────────
    if not _link_number(ctx, phone, customer=subject):
        return

    say("Hi")                              # opens the conversation + bot session
    say("I want to verify a property")     # a flow, so the session holds context
    say("1")
    intake_prompt = say("7 Bourdillon Road, Ikoyi")
    check("the erasure subject leaves a half-finished intake behind (§26.8)",
          bool(intake_prompt), intake_prompt[:120])

    # A status question, phrased so it reaches CHECK_STATUS rather than falling through to
    # the unmatched counter — the same question is asked again after the erasure, and the
    # comparison is only worth anything if both turns reach the same flow.
    linked_reply = say("what is the status of my case?")
    check("the number answers as a linked customer before erasure",
          "link my account" not in linked_reply.lower(), linked_reply[:200])

    # ── §4.11 erasure, executed ───────────────────────────────────────────────────
    req = subject.post("/users/me/erasure-requests",
                       json={"reason": "Erase my WhatsApp history too"}).json()["data"]
    admin.post(f"/admin/erasure-requests/{req['id']}/approve").raise_for_status()
    executed = admin.post(f"/admin/erasure-requests/{req['id']}/execute")
    check("the WhatsApp-linked subject's erasure executes (§4.11)",
          executed.status_code == 200
          and executed.json()["data"]["status"] == "EXECUTED",
          f"http {executed.status_code}: {executed.text[:200]}")
    if executed.status_code != 200:
        return

    # The audit row is keyed on the erasure request, which is the only id that tells this
    # subject's erasure apart from the one `stage_compliance` executed earlier in the run.
    actions = admin.get("/admin/audit/actions",
                        params={"action_types": ["DATA_ERASURE_EXECUTED"]}).json()["data"]
    audit_row = next((a for a in actions["items"] if a.get("resourceId") == req["id"]), None)
    surfaces = (audit_row or {}).get("details", {}).get("surfaces", [])
    # Named individually because a partial scrub is the failure mode that looks like
    # success: the account is gone, and the number is still readable.
    for table in ("whatsapp_links", "whatsapp_bot_sessions", "whatsapp_inbound_messages"):
        check(f"erasure reaches {table} (§26.8, WA-42)", table in surfaces, f"surfaces={surfaces}")

    # ── The proof that matters: what the bot does on the next message ─────────────
    # `whatsapp_links.phone_e164` going to NULL is not an implementation detail here — it
    # is the difference between a severed identity and one the channel can still resolve.
    # The erasure dropped the bot session too, so this number is new again and §26.6.1's
    # welcome answers the first turn on its own — the question has to be asked after it.
    greeting = say("Hello")
    check("an erased number starts a fresh conversation, not a resumed one (§26.8)",
          "welcome" in greeting.lower(), greeting[:200])
    after = say("what is the status of my case?")
    check("the erased number is a stranger to the bot again (§26.8)",
          "link my account" in after.lower(), after[:240])

    # Identity severed, content retained — the other half of §26.8's line, and the half an
    # over-eager scrub would break by deleting the case trail with the person.
    check("the case's audit trail survives the erasure — content is retained (§26.8)",
          "TRANSITION" in pack_for(case_id))
    check("the erased subject can no longer authenticate (§4.11)",
          login_status(subject_email, QA_PASSWORD) != 200)
