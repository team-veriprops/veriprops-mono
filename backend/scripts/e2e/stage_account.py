"""Stage — the account a user manages for themself (§1–§3, §9, §12.4).

Every self-service surface outside the verification pipeline: the absent server signup draft,
profile completion, the customer persona, setting and changing a password (and what that
does to other sessions), linked social providers, the security log, the cross-portal summary,
legal documents and consent history, notification preferences and read receipts, address
lookup, and the portal summary.

Runs on a dedicated account so changing its password disturbs no other stage; the read
receipts and portal summary use the fresh customer from `stage_onboarding`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .harness import QA_PASSWORD, Ctx, check, client, consent_version_for, login, login_status, signup_fresh_user

_NEW_PASSWORD = "Changed1234!"


def run(ctx: Ctx) -> None:
    _signup_draft()
    account, email = signup_fresh_user("qa-account")
    _identity_surfaces(account)
    _legal_and_consents(account)
    _password(account, email)
    _notification_preferences(account)
    _read_receipts(ctx)
    _address_lookup_and_summary(ctx)


def _signup_draft() -> None:
    """A half-finished signup resumes from the browser alone; the server holds nothing (§1.1).

    Anything keyed on an email before the account exists is readable by whoever types that
    email, so the server must not offer a draft to read back at all.
    """
    anon = client()
    probe = anon.get("/users/auth/signup/draft", params={"email": "qa-draft@veriprops.io"})
    check("the server keeps no signup draft an anonymous caller could read back (§1.1)",
          probe.status_code in (404, 405), f"http {probe.status_code}: {probe.text[:160]}")


def _identity_surfaces(account) -> None:
    """Linked providers, the customer persona, profile completion, the cross-portal summary."""
    links = account.get("/users/auth/oauth/links")
    check("a password account lists no linked social providers (§1.2)",
          links.status_code == 200 and links.json()["data"] == [], f"http {links.status_code}: {links.text[:120]}")
    unlink = account.delete("/users/auth/oauth/links/google")
    check("unlinking a provider is allowed while the account has a password (§1.2)",
          unlink.status_code == 200, f"http {unlink.status_code}: {unlink.text[:120]}")

    persona = account.post("/users/auth/personas/customer")
    personas = persona.json()["data"]["user"]["personas"] if persona.status_code == 200 else None
    check("taking up the customer hat again is idempotent and rotates the session (§3.2)",
          personas is not None and personas.count("CUSTOMER") == 1, f"http {persona.status_code}: {personas}")

    phone = f"81{uuid.uuid4().int % 10**8:08d}"
    completed = account.post("/users/auth/profile/complete", json={
        "country_code": "NG", "dial_code": "+234", "phone": phone,
        "country_of_residence": "NG", "timezone": "Africa/Lagos", "preferred_currency": "NGN",
    })
    user = completed.json()["data"]["user"] if completed.status_code == 200 else {}
    check("profile completion records the phone and residence (§1.2)",
          user.get("phone") == phone and user.get("countryOfResidence") == "NG",
          f"http {completed.status_code}: {completed.text[:160]}")

    summary = account.get("/users/auth/cross-portal/summary").json()["data"]
    check("the cross-portal summary covers every persona the account holds (§3.2)",
          [p["persona"] for p in summary["personas"]] == ["CUSTOMER"], f"summary={summary}")


def _legal_and_consents(account) -> None:
    """A published legal document by slug, re-accepting consent, and the consent history (§3.2, §19)."""
    documents = client().get("/users/auth/consents/documents").json()["data"]["documents"]
    terms = next(d for d in documents if d["type"] == "PLATFORM_TERMS")
    slug = terms["href"].rsplit("/", 1)[-1]
    doc = client().get(f"/users/auth/consents/documents/{slug}")
    check("a legal document is served by its slug with its body, signed out (§3.2)",
          doc.status_code == 200 and doc.json()["data"]["type"] == "PLATFORM_TERMS" and bool(doc.json()["data"]["body"]),
          f"http {doc.status_code}")

    now = datetime.now(timezone.utc).isoformat()
    accepted = account.post("/users/auth/consents/accept", json={"consents": [
        {"document_type": "PLATFORM_TERMS", "consent_version": consent_version_for("PLATFORM_TERMS"), "accepted_at": now},
    ]})
    check("accepting the current terms again is recorded (§3.2)", accepted.status_code == 200,
          f"http {accepted.status_code}: {accepted.text[:160]}")
    history = account.get("/users/auth/consents/history").json()["data"]
    types = [i["documentType"] for i in history["items"]]
    check("the consent history lists every acceptance, the re-acceptance included (§19)",
          types.count("PLATFORM_TERMS") >= 2 and "PRIVACY_POLICY" in types, f"types={types}")


def _password(account, email: str) -> None:
    """Changing a password needs the current one, and signs out every other session (§1.3)."""
    other_device = login(email, QA_PASSWORD)

    missing = account.post("/users/auth/password/set", json={"password": _NEW_PASSWORD})
    check("changing a password without the current one is refused (§1.3)",
          missing.status_code == 422, f"http {missing.status_code}: {missing.text[:160]}")
    wrong = account.post("/users/auth/password/set", json={"password": _NEW_PASSWORD, "current_password": "Wrong1234!"})
    check("a wrong current password is refused (§1.3)", wrong.status_code == 422,
          f"http {wrong.status_code}: {wrong.text[:160]}")
    events = account.get("/users/auth/sessions/security/events").json()
    check("the refused change is in the security log despite the refusal (§1.3)",
          any(e["type"] == "PASSWORD_CHANGE_REFUSED" for e in events["items"]),
          f"types={[e['type'] for e in events['items']]}")

    changed = account.post("/users/auth/password/set", json={"password": _NEW_PASSWORD, "current_password": QA_PASSWORD})
    check("the right current password changes it (§1.3)", changed.status_code == 200,
          f"http {changed.status_code}: {changed.text[:160]}")
    check("the old password no longer signs in (§1.3)", login_status(email, QA_PASSWORD) == 401)
    check("the new password signs in (§1.3)", login_status(email, _NEW_PASSWORD) == 200)
    refresh = other_device.post("/users/auth/sessions/current")
    check("every other session was signed out by the change (§1.3)", refresh.status_code == 401,
          f"http {refresh.status_code}")
    still = account.get("/users/auth/sessions/current")
    check("the session that made the change stays signed in (§1.3)", still.status_code == 200
          and still.json()["data"] is not None, f"http {still.status_code}")
    events = account.get("/users/auth/sessions/security/events").json()
    types = [e["type"] for e in events["items"]]
    check("the change and the sign-ins either side of it are in the security log (§1.3)",
          "PASSWORD_CHANGED" in types and "LOGIN_FAILURE" in types and events["meta"]["total"] == len(types),
          f"types={types}")


def _notification_preferences(account) -> None:
    """The backend owns what a user may switch off, and how (§12.4)."""
    prefs = {p["eventType"]: p for p in account.get("/notification-preferences").json()["data"]}
    check("a customer is offered customer events and not agent ones (§12.4)",
          "PAYMENT_CONFIRMED" in prefs and "NEW_JOB" not in prefs, f"events={sorted(prefs)}")
    report = prefs.get("REPORT_READY", {})
    check("the report email is always sent; only its text can be switched off (§12.4, WA-35)",
          (report.get("emailMode"), report.get("smsMode"), report.get("emailEnabled")) == ("REQUIRED", "OPTIONAL", True),
          f"report={report}")

    saved = account.put("/notification-preferences", json={
        "eventType": "PAYMENT_CONFIRMED", "emailEnabled": False, "smsEnabled": True})
    after = {p["eventType"]: p for p in account.get("/notification-preferences").json()["data"]}
    check("an opt-out is recorded and shown back (§12.4)",
          saved.status_code == 200 and after["PAYMENT_CONFIRMED"]["emailEnabled"] is False
          and after["PAYMENT_CONFIRMED"]["smsEnabled"] is True, f"http {saved.status_code}")
    foreign = account.put("/notification-preferences", json={
        "eventType": "NEW_JOB", "emailEnabled": False, "smsEnabled": False})
    check("an event not addressed to the user is refused (§12.4)", foreign.status_code == 422,
          f"http {foreign.status_code}")
    junk = account.put("/notification-preferences", json={
        "eventType": "NOT_AN_EVENT", "emailEnabled": False, "smsEnabled": False})
    check("an unknown event type is refused (§12.4)", junk.status_code == 422, f"http {junk.status_code}")


def _read_receipts(ctx: Ctx) -> None:
    """Marking one notification read, then all of them (§12.1)."""
    customer = ctx.customer
    items = customer.get("/notifications").json()["data"]["items"]
    unread = [n for n in items if not n["read"]]
    before = customer.get("/notifications/unread").json()["data"]["count"]
    if unread:
        one = customer.post(f"/notifications/{unread[0]['id']}/read").json()["data"]
        check("marking one notification read drops the unread count by one (§12.1)",
              one["count"] == before - 1, f"before={before} after={one['count']}")
    else:
        check("the fresh customer has unread notifications to mark (§12.1)", False, "none unread")
    everything = customer.post("/notifications/read-all").json()["data"]
    check("marking all read leaves nothing unread (§12.1)", everything["count"] == 0,
          f"updated={everything['updated']} count={everything['count']}")


def _address_lookup_and_summary(ctx: Ctx) -> None:
    """Address search for the submission wizard, and the portal home summary (§5, §9)."""
    suggestions = ctx.customer.get("/verifications/geo/autocomplete", params={"q": "lekki"}).json()["data"]
    check("address search suggests matching places (§5.1)",
          any(s["placeId"] == "stub-lekki" for s in suggestions), f"suggestions={suggestions}")
    place = ctx.customer.get("/verifications/geo/place/stub-lekki").json()["data"]
    check("a chosen place resolves to its state and LGA (§5.1)",
          place is not None and (place["state"], place["lga"]) == ("Lagos", "Eti-Osa"), f"place={place}")

    summary = ctx.customer.get("/verifications/summary").json()["data"]
    check("the portal summary counts the customer's verifications server-side (§9)",
          summary["total"] >= 1 and summary["total"] == sum(summary["statusCounts"].values()),
          f"summary={summary}")
