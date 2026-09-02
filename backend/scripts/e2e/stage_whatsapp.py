"""Stage — WhatsApp channel (S1–S7, PRD §7).

Drives the channel over HTTP the way the outside world does. Five things here cannot be
proved by unit tests, and all of them are load-bearing:

* **The webhook is the real entry point.** It is signed with a real HMAC over the raw
  body, so this stage signs its own fixtures rather than injecting through the dev door.
  A tampered body must be refused.
* **Redelivery is safe in the database, not just in a mock.** Meta retries until it gets a
  2xx; the unique ``wamid`` index is what turns a retry into a no-op, and only a live
  Postgres can demonstrate that.
* **A handoff link really pays.** §7.10 calls intake→payment the channel's most important
  number, so the stage carries a `pay` token all the way to a PAID verification.
* **An agent's console reply really leaves the building.** For two commits it did not: the
  message was written into the thread and delivered nowhere, and this stage asserted only
  that the thread flipped to `HUMAN` — which passed the whole time. The outbox assertion
  is the one that would have caught it.
* **The customer is answered whatever they send.** §7.6.3's three rows are exercised
  against the real ingestion path, including the photo case that used to be answered
  with "Sorry, I didn't quite get that".

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
    CONSENT_VERSION,
    TEST_OTP,
    Ctx,
    check,
    client,
    idem_key,
    pin_cookie_header,
    warn,
)

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

    # ── S1: one config source for the official number (§7.1.2, WA-02) ──────────
    cfg = root.get("/config/public").json()["data"]
    check("public config serves the official WhatsApp number (§7.1.2)",
          cfg.get("whatsappNumber", "").isdigit() and len(cfg["whatsappNumber"]) > 10,
          f"number={cfg.get('whatsappNumber')}")
    check("the number is also served in its human-readable form",
          cfg.get("whatsappDisplayNumber", "").startswith("+"),
          f"display={cfg.get('whatsappDisplayNumber')}")
    check("the widget kill switch is exposed to the frontend (§7.4.1)",
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

    # ── §7.7: the template registry the launch gate reads ────────────────────
    _run_template_registry_checks(ctx)

    # ── S5: the bot actually answers, and refuses what it must ───────────────
    _run_bot_checks(ctx)

    # ── S6: a chat intake becomes a real draft on the website ────────────────
    _run_intake_checks(ctx)

    # ── S7: §7.6.3 — every non-text type answered per the table ──────────────
    _run_media_checks(ctx)


def _run_webhook_checks(ctx: Ctx) -> None:
    root = ctx.root

    # The subscription handshake Meta performs before it will deliver anything.
    challenge = str(uuid.uuid4().int % 10**10)
    r = root.get("/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": _VERIFY_TOKEN, "hub.challenge": challenge,
    })
    check("webhook echoes Meta's subscription challenge (§7.3.3)",
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
    check("signed Meta delivery accepted (§7.3.3, WA-09)", r.status_code == 200,
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
    check("the thread is keyed on the sender's number, not an account (§7.4.4)",
          str(thread.get("externalRef", "")).endswith(_CUSTOMER_PHONE[-10:]),
          f"externalRef={thread.get('externalRef')}")

    msgs = admin.get(f"/chat/conversations/{thread['id']}/messages").json()["data"]["items"]
    check("console messages are labelled with the surface they arrived on (§7.3.3)",
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

    # §7.6.3: non-text is journalled and labelled, never silently dropped.
    root.post("/dev/whatsapp/inbound", json={"fromPhone": _CUSTOMER_PHONE, "kind": "AUDIO"}).raise_for_status()
    msgs = admin.get(f"/chat/conversations/{thread['id']}/messages").json()["data"]["items"]
    check("a voice note reaches the console labelled, never dropped (§7.6.3)",
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

    # 1. Redeeming lands the customer on their case, with context (§7.4.2).
    token = mint("pay")
    holder = client()
    r = holder.post(f"/public/wa/handoff/pay/{token}/redeem")
    check("a pay link redeems without a session (§7.5 — the token is the authorization)",
          r.status_code == 200, f"http {r.status_code}: {r.text[:160]}")
    # The grant is a Secure cookie and this runs over plain http (see the harness).
    pin_cookie_header(holder)
    context = r.json()["data"]
    check("the landing is told which case it is picking up (§7.4.2)",
          context.get("vid", "").startswith("VP-"), f"context={context}")
    check("the landing is told what is owed", (context.get("amountDueMinor") or 0) > 0)

    # 2. A forwarded copy is dead — a different client, same link.
    r = client().post(f"/public/wa/handoff/pay/{token}/redeem")
    check("a forwarded copy of a spent link is refused (§7.5 single-use)",
          r.status_code == 404, f"http {r.status_code}")

    # 3. …but the customer who redeemed it may reload their own page (D51).
    r = holder.post(f"/public/wa/handoff/pay/{token}/redeem")
    check("the original holder can reload their landing (D51 grant)",
          r.status_code == 200, f"http {r.status_code}: {r.text[:160]}")

    # 4. A link is scoped to one action: a report link is not a payment authorization.
    r = client().post(f"/public/wa/handoff/pay/{mint('report')}/redeem")
    check("a report link presented at the pay landing is refused (§7.5 scope)",
          r.status_code == 404, f"http {r.status_code}")

    # 5. Garbage and a spent link are indistinguishable from outside.
    r = client().post("/public/wa/handoff/pay/not-a-real-token/redeem")
    check("an invalid link fails exactly like a spent one (no oracle)",
          r.status_code == 404, f"http {r.status_code}")

    # 6. The seam that matters: the handoff actually pays (§7.10).
    r = holder.post("/public/wa/handoff/pay/initiate")
    check("the grant starts a real payment for the case it names (§7.4.2, Decision A)",
          r.status_code == 200, f"http {r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        return
    payment = r.json()["data"]
    check("the handoff payment carries a gateway reference", bool(payment.get("txRef")))

    r = customer.post("/payments/stub/confirm",
                      json={"txRef": payment["txRef"], "succeeded": True})
    check("a WhatsApp-originated payment completes (§7.10 seam conversion)",
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
    """§7.4.4 account linking, end to end on the stub transport (WA-23/WA-24/WA-25).

    Three things cannot be proved without a live stack, and all three are the point of
    the slice: the code really goes out over **WhatsApp** (the stub outbox is the
    evidence), the console thread this number has been talking in really gains an owner
    rather than a second thread appearing, and unlinking really releases the number so
    another account could claim it.
    """
    root, customer, admin = ctx.root, ctx.customer, ctx.admin

    link = customer.get("/channel/whatsapp/link/me").json()["data"]
    check("a fresh account starts with no WhatsApp link (§7.4.4)",
          link.get("status") != "ACTIVE" and not link.get("phoneE164"), f"link={link}")

    root.delete("/dev/whatsapp/outbox")
    r = customer.post("/channel/whatsapp/link/me/start",
                      json={"phoneE164": f"+{_CUSTOMER_PHONE}"})
    check("starting a link is accepted (§7.4.4, WA-23)", r.status_code == 200,
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

    # §7.7/D59b: an OTP to a number that has never messaged us is outside Meta's 24-hour
    # window, so it must go as the approved **template** — free text would be rejected
    # live. The stub records both halves, which is the only place this is observable.
    templated = [m for m in messages if m.get("templateName") == "otp_auth"]
    check("the linking OTP is sent as the §7.7 `otp_auth` template, not free text",
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
    check("a pending attempt is not yet a link (§7.4.4)", pending.get("status") == "PENDING",
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

    # §7.8: one conversation object per person — the *existing* thread gains an owner.
    threads = admin.get("/chat/conversations").json()["data"]
    wa_threads = [t for t in threads if t.get("channel") == "WHATSAPP"
                  and str(t.get("externalRef", "")).endswith(_CUSTOMER_PHONE[-10:])]
    check("linking adopts the existing thread instead of opening a second one (§7.8)",
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
    """§7.7 template registry (WA-15/WA-41).

    The §7.11 launch gate turns on "all §7.7 templates approved", so the operational
    question is whether an admin can actually see that answer. Under the stub the
    directory reports the declared set as approved, which is what makes the whole channel
    demoable without Meta — the live directory is the same interface behind a different
    transport.
    """
    admin, customer = ctx.admin, ctx.customer

    registry = admin.get("/admin/config/whatsapp-templates").json()["data"]
    check("the admin registry lists all seven §7.7 templates (WA-15)",
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
    """The bot engine over the wire (§7.6, WA-11/WA-39).

    Unit tests already pin the gauntlet's branching. What only a live stack proves is that
    a message posted at the webhook comes back out of the **stub transport** as a real
    outbound reply — the whole path through ingestion, the session row, the classifier
    facade, the conversation mirror and the provider. Three of the four faults that killed
    the outbound path before were invisible to unit tests for exactly that reason.

    A fresh number, so the welcome is genuinely a first contact: §7.6.1 short-circuits
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

    # §7.6.1 — first contact opens with the disclosure and the payment pledge.
    replies = say("Hi")
    check("the bot answers a first message over the real transport (§7.6.1)",
          len(replies) == 1, f"outbound={len(replies)}")
    if not replies:
        warn("bot drive-through stopped", "no outbound reply to assert against")
        return
    welcome = str(replies[0].get("text", ""))
    check("the welcome discloses that it is a bot (§7.1.4)",
          "automated assistant" in welcome, welcome[:120])
    check("the welcome carries the payment pledge (§7.1.1)",
          "veriprops.ng" in welcome and "address bar" in welcome, welcome[:160])

    # The menu it just offered has to work — a number is the one input it invited.
    replies = say("5")
    pricing = str(replies[0].get("text", "")) if replies else ""
    check("a menu number is answered deterministically (§7.6.1)",
          "₦" in pricing, pricing[:120])
    check("pricing is quoted from the live admin config, not from copy (D54)",
          "per property" in pricing, pricing[:160])

    # §7.6.4 — the guardrail that matters most, over the wire rather than in a unit test.
    replies = say("Is this land genuine? Should I buy it?")
    verdict = str(replies[0].get("text", "")) if replies else ""
    check("the bot refuses to judge a property and routes to a person (§7.6.4)",
          "our verifiers" in verdict or "team" in verdict, verdict[:160])
    check("the refusal renders no verdict of its own (§7.1.3)",
          not any(word in verdict.lower() for word in ("looks genuine", "seems fine", "is safe")),
          verdict[:160])

    # §7.4.3 — an unlinked number is never read case data.
    replies = say("What is the status of my verification?")
    status = str(replies[0].get("text", "")) if replies else ""
    check("an unlinked number is refused case data and offered linking (§7.4.3)",
          "isn't linked" in status, status[:160])

    # §7.6.3 — a voice note is acknowledged and handed over, never ignored. Its own copy
    # since S7: "a team member will listen" is the row's promise, and pooling it with the
    # media the bot merely cannot open lost both the wording and the §7.10 count.
    replies = say("", kind="AUDIO")
    audio = str(replies[0].get("text", "")) if replies else ""
    check("a voice note is acknowledged and handed to a person (§7.6.3)",
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
        check("the console can see that Meta's reply window is open (§7.7)",
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
    check("the launch gate can read the channel's configuration (§7.11)",
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
    """Meta's 24-hour service window on a late agent reply (§7.7, WA-41).

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
    check("an aged conversation reads as outside Meta's window (§7.7)",
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
    check("the queued reply is marked as undelivered in the console (§7.7)",
          any("survey came back clean" in m["body"] for m in queued),
          f"queued={[m['body'][:40] for m in queued]}")

    # One nudge per closed-window episode: three messages must not cost three templates.
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    admin.post(f"/chat/conversations/{conversation_id}/messages",
               json={"body": "Let me know when you're free to talk."}).raise_for_status()
    outbound = _outbound_to(ctx, phone)
    check("a second late reply joins the queue without a second nudge (§7.7)",
          not any("replied to your enquiry" in str(m.get("text", "")) for m in outbound),
          f"outbound={[str(m.get('text'))[:60] for m in outbound]}")

    # The customer answers: the window reopens and the queue flushes, in order.
    root.delete("/dev/whatsapp/outbox").raise_for_status()
    root.post("/dev/whatsapp/inbound", json={
        "fromPhone": phone, "text": "Sorry, just seeing this now",
    }).raise_for_status()
    delivered = [str(m.get("text", "")) for m in _outbound_to(ctx, phone)]
    check("the customer's reply flushes everything the agent queued (§7.7)",
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
    """§7.6.3 non-text inbound, end to end (WA-06, WA-38).

    The regression this pins is small and embarrassing: image kinds were left out of the
    bot's unreadable set on the assumption the upload handoff would catch them, and the
    handoff had not been built — so a customer photographing their survey plan was
    answered with "Sorry, I didn't quite get that".

    The evidence rule (§7.1.6) is the other half. A document sent here is redirected to
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

    # A fresh number, so §7.6.1's welcome does not answer the turn we are testing.
    root.post("/dev/whatsapp/inbound", json={"fromPhone": phone, "text": "Hi"}).raise_for_status()

    # An unlinked number: the evidence rule still applies, but no upload link — a token
    # names a customer *and* a case, and a phone number alone identifies neither (§7.4.3).
    unlinked = send("IMAGE")
    check("a photo from an unlinked number is answered with the evidence rule (§7.1.6)",
          "verification file" in unlinked, unlinked[:200])
    check("an unlinked number is never handed an upload link (§7.4.3)",
          "/wa/upload/" not in unlinked, unlinked[:200])

    # §7.6.3 row two — a voice note is acknowledged with its own copy, never dropped.
    voice = send("AUDIO")
    check("a voice note is promised a person who will listen (§7.6.3)",
          "listen" in voice, voice[:200])
    session = admin.get(f"/admin/whatsapp/bot/sessions/{phone}").json()["data"]
    check("a voice note is counted under its own escalation reason (§7.10)",
          session.get("lastEscalationReason") == "VOICE_NOTE",
          f"reason={session.get('lastEscalationReason')}")

    # §7.6.3 row three — a pin goes to a person.
    pin = send("LOCATION")
    check("a location pin is acknowledged and routed to a person (§7.6.3)",
          bool(pin) and "team member" in pin, pin[:200])

    # The console's own view: labelled, and labelled as not-evidence.
    threads = admin.get("/chat/conversations").json()["data"]
    thread = next((t for t in threads if str(t.get("externalRef", "")).endswith(phone[-10:])), None)
    check("the media thread is in the console", thread is not None)
    if thread:
        msgs = admin.get(f"/chat/conversations/{thread['id']}/messages").json()["data"]["items"]
        media = [m for m in msgs if m.get("mediaKind")]
        check("non-text inbound carries what it was, for the console to flag (§7.6.3)",
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
    check("a document with several open cases is asked about, never guessed (§7.6.3)",
          "which one" in linked.lower(), linked[:240])
    check("the choice lists the customer's own references",
          "VP-" in linked, linked[:240])

    linked = say("1")
    check("a linked customer's photo earns an upload link (§7.6.3, WA-38)",
          "/wa/upload/" in linked, linked[:240])
    check("the upload answer still states the evidence rule",
          "verification file" in linked, linked[:240])

    if "/wa/upload/" in linked:
        token = linked.split("/wa/upload/")[1].split()[0].strip()
        holder = client()
        redeemed = holder.post(f"/public/wa/handoff/upload/{token}/redeem")
        check("the upload link opens the customer's own case (§7.5)",
              redeemed.status_code == 200, f"http {redeemed.status_code}: {redeemed.text[:160]}")
        replay = client().post(f"/public/wa/handoff/upload/{token}/redeem")
        check("a spent upload link is dead, like every other handoff link (§7.5)",
              replay.status_code == 404, f"http {replay.status_code}")

    # Leave the customer unlinked, as `_run_linking_checks` does: the 1:1 rule means a
    # stray link would refuse whatever a later stage tries to claim.
    customer.delete("/channel/whatsapp/link/me")


def _link_number(ctx: Ctx, phone: str) -> bool:
    """Link *phone* to the stage's customer so case-scoped flows can be exercised."""
    customer = ctx.customer
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

    say("Hi")  # §7.6.1 welcome, which answers the turn on its own
    opening = say("I want to verify a property")
    check("a stranger can start an intake with no account (§7.3.4, D69)",
          "what are you verifying" in opening.lower(), opening[:120])

    location_prompt = say("1")
    check("the intake asks where the property is (§5.1)",
          "where is the" in location_prompt.lower(), location_prompt[:120])

    state_prompt = say("12 Ademola Street, Ikeja")
    check("the intake asks for the state", "state" in state_prompt.lower(), state_prompt[:120])

    tier_prompt = say("Lagos")
    check("the tier prompt quotes live prices (D54)", "₦" in tier_prompt, tier_prompt[:160])

    handoff = say("2")
    check("completing the intake hands off with a single-use link (§7.5)",
          "/wa/intake/" in handoff, handoff[:200])
    check("the handoff repeats the payment pledge (§7.1.1)",
          "veriprops.ng" in handoff and "address bar" in handoff, handoff[:200])

    token = handoff.split("/wa/intake/")[1].split()[0].strip()

    # The landing is authenticated (D69): the token carries a conversation, the session
    # says whose draft it becomes.
    unauthenticated = client()
    refused = unauthenticated.post(f"/wa/intake/{token}/redeem")
    check("the intake landing refuses an anonymous caller (D69)",
          refused.status_code in (401, 403), f"http {refused.status_code}")

    redeemed = customer.post(f"/wa/intake/{token}/redeem")
    check("a signed-in customer redeems the intake link (§7.5)",
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

    # Single-use, like every other §7.5 link.
    replay = customer.post(f"/wa/intake/{token}/redeem")
    check("a spent intake link is dead (§7.5)",
          replay.status_code == 404, f"http {replay.status_code}")


def _create_payable_case(ctx: Ctx) -> str:
    """A SUBMITTED verification for the fresh customer — the state a pay link targets."""
    customer = ctx.customer
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
        "consent": {"consent_version": CONSENT_VERSION},
    })
    check("created a payable case for the WhatsApp handoff", r.status_code == 200,
          f"submit http {r.status_code}: {r.text[:200]}")
    return case_id if r.status_code == 200 else ""
