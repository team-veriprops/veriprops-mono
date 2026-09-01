"""Stage — WhatsApp channel (S1–S3, PRD §7).

Drives the channel over HTTP the way the outside world does. Three things here cannot be
proved by unit tests, and all three are load-bearing:

* **The webhook is the real entry point.** It is signed with a real HMAC over the raw
  body, so this stage signs its own fixtures rather than injecting through the dev door.
  A tampered body must be refused.
* **Redelivery is safe in the database, not just in a mock.** Meta retries until it gets a
  2xx; the unique ``wamid`` index is what turns a retry into a no-op, and only a live
  Postgres can demonstrate that.
* **A handoff link really pays.** §7.10 calls intake→payment the channel's most important
  number, so the stage carries a `pay` token all the way to a PAID verification.

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

from .harness import CONSENT_VERSION, Ctx, check, client, idem_key, pin_cookie_header, warn

# The webhook secret is Doppler-managed and absent from committed env files, so the
# signature checks run only when the operator started the backend with one and exported
# the same value here — the same opt-in shape as ENABLE_OUT_MESSAGING for the email
# stage. Everything downstream of the webhook is exercised either way, through the dev
# injection endpoint.
_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET_KEY", "")
_VERIFY_TOKEN = os.environ.get("WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN", "")
_PLACEHOLDERS = {"", "CHANGE_ME"}
_CUSTOMER_PHONE = "2348012345678"


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
    wa_threads = [t for t in threads if t.get("channel") == "WHATSAPP"]
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
