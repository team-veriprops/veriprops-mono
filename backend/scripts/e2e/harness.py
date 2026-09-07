"""Shared harness for the live e2e drive-through stages.

One copy of the plumbing every stage needs: the PASS/FAIL ``check`` accumulator, the
``login`` helper (with the ``__Host-`` cookie → header pinning + double-submit CSRF
workaround for plain-http runs), the deterministic stub-payment confirmer, and the
``Ctx`` object that threads clients + ids between stages.
"""
from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://localhost:8000/api"
TEST_OTP = "654123"  # deterministic OTP (OTP_MODE=deterministic in non-prod)
QA_PASSWORD = "Test1234!"  # the dev-seed password for customer/agents

# Current consent version per document type, read from the backend rather than pinned.
# The versions differ by document — migration 0011 moved PLATFORM_TERMS, PRIVACY_POLICY and
# COMMUNICATION_RECORDING to 1.1.0 for the §26.8 clauses while the rest stayed at 1.0.0 — so
# the single literal that used to live here signed the wrong version for two of the three
# documents signup sends. Nothing failed: the account is created and `/consents/missing`
# quietly reports both as still owed, which is a state no real signup can reach. Backend is
# the source of truth (CLAUDE.md rule 5), and this survives the next version bump for free.
_consent_versions: Optional[Dict[str, str]] = None


def consent_version_for(document_type: str) -> str:
    """The published consent version for one document type, fetched once per run."""
    global _consent_versions
    if _consent_versions is None:
        r = client().get("/users/auth/consents/documents")
        r.raise_for_status()
        _consent_versions = {
            d["type"]: d["consentVersion"] for d in r.json()["data"]["documents"]
        }
    return _consent_versions[document_type]


def signup_consents(now: str) -> list[dict]:
    """The consent block every signup posts — the two documents §3.2 requires at signup."""
    return [
        {"document_type": t, "consent_version": consent_version_for(t), "accepted_at": now}
        for t in ("PLATFORM_TERMS", "PRIVACY_POLICY")
    ]

_failures: list[str] = []
# Every assertion the run made, passing or not. Counted rather than inferred: the totals
# quoted in docs/runtime-state.yaml used to be hand-counted from [PASS] lines, which is
# both tedious and quietly wrong the moment a stage warn-skips.
_checks = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        _failures.append(name)


def warn(name: str, detail: str = "") -> None:
    """Non-fatal observation (e.g. an SSE probe that timed out waiting for an event)."""
    print(f"[WARN] {name}" + (f" — {detail}" if detail else ""))


def failures() -> list[str]:
    return _failures


def checks_run() -> int:
    """How many assertions this run actually made."""
    return _checks


def client() -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=30.0)


def pin_session_cookies(c: httpx.Client) -> None:
    """The session uses ``__Host-``-prefixed Secure cookies; httpx won't resend a Secure
    cookie over plain http, so pin the jar's cookies onto an explicit Cookie header.
    Mutations also require the access CSRF token as a header (double-submit)."""
    jar = {k: v for k, v in c.cookies.items()}
    if jar:
        c.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
    csrf = jar.get("__Host-access_csrf_token")
    if csrf:
        c.headers["X-CSRF-Token"] = csrf


def pin_cookie_header(c: httpx.Client) -> None:
    """Pin whatever the jar holds onto an explicit Cookie header.

    Same reason as ``pin_session_cookies``: these are ``Secure`` cookies and the
    drive-through runs over plain http, so httpx will not resend them on its own. Used
    for the WhatsApp handoff grant, which is how a redeemed landing survives a reload.
    """
    jar = {k: v for k, v in c.cookies.items()}
    if jar:
        c.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())


def login(email: str, password: str) -> httpx.Client:
    c = client()
    c.post("/users/auth/sessions", json={"email": email, "password": password}).raise_for_status()
    pin_session_cookies(c)
    return c


def login_status(email: str, password: str) -> int:
    """Status code of a login attempt (for asserting an erased account can't log in)."""
    return client().post(
        "/users/auth/sessions", json={"email": email, "password": password}
    ).status_code


def stub_pay(c: httpx.Client, checkout_url: str) -> None:
    """Drive a charge to PAID via the deterministic stub webhook."""
    tx_ref = parse_qs(urlparse(checkout_url).query).get("txRef", [""])[0]
    c.post("/payments/stub/confirm", json={"tx_ref": tx_ref, "succeeded": True}).raise_for_status()


def idem_key() -> str:
    return uuid.uuid4().hex


def signup_fresh_user(prefix: str, *, referral_code: Optional[str] = None,
                      first_name: str = "Ada", last_name: str = "QA") -> tuple[httpx.Client, str]:
    """Drive the email-OTP → consent-gated signup funnel for a brand-new user (§2).

    Returns a session-pinned client + the generated email. Every user gets a unique
    phone — a shared verified phone is the §17.1/D34 anti-farming signal and would
    void any referral credit the run asserts on.
    """
    from datetime import datetime, timezone

    email = f"{prefix}-{uuid.uuid4().hex[:8]}@veriprops.io"
    now = datetime.now(timezone.utc).isoformat()
    root = client()
    r = root.post("/users/auth/otp/send", json={"channel": "EMAIL", "email": email,
                                                "fullname": f"{first_name} {last_name}"})
    check(f"email OTP send accepted for {prefix} (§2)", r.status_code == 200, f"http {r.status_code}")
    r = root.post("/users/auth/otp/verify", json={"channel": "EMAIL", "email": email, "code": TEST_OTP})
    check(f"email OTP verified for {prefix} (§2)", r.status_code == 200
          and r.json()["data"].get("verified") is True, f"http {r.status_code}")

    c = client()
    r = c.post("/users/auth/signup", json={
        "first_name": first_name, "last_name": last_name, "email": email, "password": QA_PASSWORD,
        "country_code": "NG", "dial_code": "+234", "phone": f"81{uuid.uuid4().int % 10**8:08d}",
        "country_of_residence": "NG", "timezone": "Africa/Lagos", "preferred_currency": "NGN",
        "referral_code": referral_code,
        "consents": signup_consents(now),
    })
    check(f"signup created the {prefix} account + session (Phase 2)", r.status_code in (200, 201),
          f"http {r.status_code}: {r.text[:200]}")
    pin_session_cookies(c)

    # Signing the *current* version is what makes this a real signup. Posting a stale one
    # still creates the account, so the only thing that catches the drift is asking the
    # backend whether it considers the paperwork done.
    missing = c.get("/users/auth/consents/missing")
    owed = missing.json()["data"]["documents"] if missing.status_code == 200 else None
    check(f"the {prefix} signup owes no consent afterwards (§3.2)", owed == [],
          f"http {missing.status_code}: {owed}")
    return c, email


# 1×1 transparent PNG — a minimal valid evidence binary for uploads.
MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffffff7f000705fe02fea72d874e0000000049454e44ae426082"
)


@dataclass
class Ctx:
    """Mutable run state threaded through the stages (populated as stages run)."""

    root: httpx.Client
    admin: httpx.Client
    seed: Dict[str, Any]                        # raw /dev/seed payload
    seed_customer: httpx.Client                 # the seeded (referrer) customer
    # Fresh cradle-to-grave actors/ids — set by stage_onboarding onward.
    customer: Optional[httpx.Client] = None     # the fresh signed-up customer
    customer_email: str = ""
    referral_code: str = ""
    vid_id: str = ""                            # fresh verification id (wire form)
    vid: str = ""                               # fresh verification VID (VP-…)
    conv_id: str = ""                           # fresh customer↔admin chat thread
    agents: Dict[str, httpx.Client] = field(default_factory=dict)   # role → client
    task_ids: Dict[str, str] = field(default_factory=dict)          # role → fresh task id
    wa_wamid: str = ""                          # the Meta message id the WhatsApp stage signed

    @property
    def seed_vid_id(self) -> str:
        """The seeded (SLA-overdue, stays UNDER_REVIEW) verification id."""
        return self.seed["verification"]["id"]

    def agent(self, role: str) -> httpx.Client:
        """Login-once client for a seeded agent by role (REGISTRY/FIELD/SURVEYOR/…)."""
        role = role.upper()
        if role not in self.agents:
            self.agents[role] = login(f"qa-agent-{role.lower()}@veriprops.io", QA_PASSWORD)
        return self.agents[role]
