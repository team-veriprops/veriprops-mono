"""Stage — the external sweep trigger (D12 follow-up): `POST /internal/sweeps/tick`.

The Cloudflare Cron Worker calls this every minute on the deployed (serverless) environments,
and it is the only thing that runs their sweeps. This drives it the way the Worker does, over
HTTP with the shared secret, and checks the three things the Worker relies on: the door is
shut to a wrong secret, a tick runs exactly the jobs that are due, and a claimed fire is not
run again by the next tick.

Needs `SWEEP_TRIGGER_SECRET` exported to **both** the backend and this script (CI sets a
throwaway one in e2e.yml). Without it the endpoint is disabled, so the stage checks the 404 and
warn-skips the rest (a failure in CI, where the secret is provisioned).
"""
from __future__ import annotations

import os

from .harness import Ctx, check, skip_unless_ci

_TICK = "/internal/sweeps/tick"
_HEADER = "x-sweep-secret"
# Harmless to run on demand: it only deletes key/value rows that have already expired.
_PROBE_JOB = "expired_key_value_cleanup"


def _tick(ctx: Ctx, secret: str):
    return ctx.root.post(_TICK, headers={_HEADER: secret})


def _outcomes(response) -> dict[str, str]:
    return {job["name"]: job["outcome"] for job in response.json()["data"]["jobs"]}


def run(ctx: Ctx) -> None:
    secret = os.environ.get("SWEEP_TRIGGER_SECRET", "").strip()
    if not secret:
        r = _tick(ctx, "anything")
        check("sweep tick is disabled (404) without SWEEP_TRIGGER_SECRET", r.status_code == 404,
              f"http {r.status_code}")
        skip_unless_ci("SWEEP_TRIGGER_SECRET not exported — sweep-tick run checks skipped",
                       "export the same SWEEP_TRIGGER_SECRET to the backend and this script")
        return

    r = _tick(ctx, secret + "-wrong")
    check("sweep tick refuses a wrong secret (401)", r.status_code == 401, f"http {r.status_code}")
    r = ctx.root.post(_TICK)
    check("sweep tick refuses a missing secret (401)", r.status_code == 401, f"http {r.status_code}")

    # /dev/reset cleared the job clock in the prologue, so the first tick anchors every job
    # now and finds none due — the deterministic baseline the next ticks are judged against.
    first = _tick(ctx, secret)
    check("sweep tick with the right secret answers 200", first.status_code == 200, f"http {first.status_code}")
    if first.status_code != 200:
        return
    outcomes = _outcomes(first)
    check("a tick reports every registered job", _PROBE_JOB in outcomes and len(outcomes) >= 12,
          f"{len(outcomes)} jobs")
    check("a freshly anchored job is not due", outcomes.get(_PROBE_JOB) == "NOT_DUE", str(outcomes.get(_PROBE_JOB)))

    rewound = ctx.root.post("/dev/sweeps/rewind", params={"name": _PROBE_JOB})
    check("dev rewind makes the probe job due", rewound.status_code == 200 and rewound.json()["data"]["rewound"],
          rewound.text[:200])

    second = _outcomes(_tick(ctx, secret))
    check("the next tick runs the due job", second.get(_PROBE_JOB) == "RAN", str(second.get(_PROBE_JOB)))
    others = {name: outcome for name, outcome in second.items() if name != _PROBE_JOB and outcome != "NOT_DUE"}
    check("…and only that job", not others, str(others))

    third = _outcomes(_tick(ctx, secret))
    check("a claimed fire is not run again by the following tick",
          third.get(_PROBE_JOB) == "NOT_DUE", str(third.get(_PROBE_JOB)))
