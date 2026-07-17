"""Stage 0 — the session-refresh contract the frontend FetchHttpClient relies on (§2).

The browser client auto-recovers from access-token expiry: on a 401 it POSTs
``/users/auth/sessions/current`` with the refresh cookie and the REFRESH CSRF token,
then retries the original request with the re-issued access cookie. A failed refresh
(wrong CSRF token, missing refresh cookie, revoked device session) must reject so the
client can hand the user to the login page instead of silently staying broken. This
stage pins that contract at the HTTP level — the happy refresh-and-retry plus every
failure class, including the access-vs-refresh CSRF mix-up that once broke silent
re-auth in the deployed frontend.

Self-contained: logs the seeded customer in on a dedicated "device" and revokes only
that session, so ``ctx.seed_customer`` and later stages are untouched.
"""
from __future__ import annotations

from typing import Dict

from .harness import Ctx, check, client

ACCESS = "__Host-access_token"
ACCESS_CSRF = "__Host-access_csrf_token"
REFRESH = "__Host-refresh_token"
REFRESH_CSRF = "__Host-refresh_csrf_token"

SESSION_PATH = "/users/auth/sessions/current"


def _cookies(jar: Dict[str, str], *names: str) -> str:
    """Explicit Cookie header (httpx won't resend ``__Host-`` Secure cookies over
    plain http, and per-scenario cookie subsets are the whole point here)."""
    return "; ".join(f"{n}={jar[n]}" for n in names if jar.get(n))


def run(ctx: Ctx) -> None:
    c = client()
    c.post("/users/auth/sessions", json={
        "email": ctx.seed["customer"]["email"],
        "password": ctx.seed["customer"]["password"],
    }).raise_for_status()
    jar = {k: v for k, v in c.cookies.items()}
    probe = client()

    r = probe.get(SESSION_PATH, headers={"Cookie": _cookies(jar, ACCESS)})
    check("a valid access cookie reaches a protected endpoint (baseline)",
          r.status_code == 200, f"http {r.status_code}")

    # An expired access token and a missing one look identical to the backend.
    r = probe.get(SESSION_PATH, headers={"Cookie": _cookies(jar, REFRESH, REFRESH_CSRF)})
    check("a missing/expired access token 401s — the client's refresh trigger",
          r.status_code == 401, f"http {r.status_code}")

    # Happy path: refresh with the REFRESH CSRF token re-issues the access cookie.
    r = probe.post(SESSION_PATH, headers={
        "Cookie": _cookies(jar, REFRESH, REFRESH_CSRF),
        "X-CSRF-Token": jar[REFRESH_CSRF],
    })
    new_access = r.cookies.get(ACCESS)
    check("refresh with the refresh CSRF token re-issues the access cookie",
          r.status_code == 200 and bool(new_access), f"http {r.status_code}")
    check("refresh leaves the refresh cookie itself untouched (no rotation)",
          not r.cookies.get(REFRESH))

    r = probe.get(SESSION_PATH, headers={"Cookie": f"{ACCESS}={new_access}"})
    check("the retried request succeeds with the re-issued access cookie",
          r.status_code == 200, f"http {r.status_code}")

    # Failure class 1 — the ACCESS CSRF token on the refresh call (the exact
    # FetchHttpClient regression this stage exists to guard against).
    r = probe.post(SESSION_PATH, headers={
        "Cookie": _cookies(jar, REFRESH, REFRESH_CSRF),
        "X-CSRF-Token": jar[ACCESS_CSRF],
    })
    check("refresh presenting the ACCESS csrf token is rejected",
          r.status_code in (401, 403) and not r.cookies.get(ACCESS), f"http {r.status_code}")

    # Failure class 2 — no refresh cookie at all (cleared / never issued).
    r = probe.post(SESSION_PATH, headers={"X-CSRF-Token": jar[REFRESH_CSRF]})
    check("refresh without a refresh cookie is rejected",
          r.status_code in (401, 403) and not r.cookies.get(ACCESS), f"http {r.status_code}")

    # Failure class 3 — a still-unexpired refresh JWT whose device session was
    # revoked (logout / device revoke / reset-time revoke-all must end sessions).
    r = probe.delete(SESSION_PATH, headers={
        "Cookie": _cookies(jar, ACCESS, ACCESS_CSRF, REFRESH, REFRESH_CSRF),
        "X-CSRF-Token": jar[ACCESS_CSRF],
    })
    check("logout revokes the current device session", r.status_code == 200, f"http {r.status_code}")
    r = probe.post(SESSION_PATH, headers={
        "Cookie": _cookies(jar, REFRESH, REFRESH_CSRF),
        "X-CSRF-Token": jar[REFRESH_CSRF],
    })
    check("a revoked device session cannot refresh (revocation enforced on refresh)",
          r.status_code in (401, 403) and not r.cookies.get(ACCESS), f"http {r.status_code}")
