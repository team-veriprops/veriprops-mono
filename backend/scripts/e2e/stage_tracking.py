"""Stage 5 — customer tracking, activity & evidence + SSE probe (S13 §9, R19.2).

Runs after release so the review-approved evidence is customer-visible (D17: evidence is
only exposed after approval). The SSE probe is best-effort route coverage: a non-200 fails,
but waiting out a quiet heartbeat window only warns — event *content* is asserted through
the notification/auto-post checks elsewhere.
"""
from __future__ import annotations

import httpx

from .harness import Ctx, check, warn


def run(ctx: Ctx) -> None:
    customer, vid_id = ctx.customer, ctx.vid_id

    page = customer.get("/verifications").json()["data"]
    check("customer verification list is paged and holds the fresh VID (§9.1)",
          any(v["id"] == vid_id for v in page["items"]), f"total={page.get('total')}")

    tracking = customer.get(f"/verifications/{vid_id}/tracking").json()["data"]
    check("tracking view reports the completed pipeline (§9.2)",
          tracking.get("status") == "COMPLETED", f"status={tracking.get('status')}")

    evidence = customer.get(f"/verifications/{vid_id}/evidence").json()["data"]
    items = evidence["items"] if isinstance(evidence, dict) else evidence
    check("review-approved evidence is customer-visible after release (§9.3, D17)",
          len(items) >= 1, f"items={len(items)}")

    activity = customer.get(f"/verifications/{vid_id}/activity").json()["data"]
    check("customer activity feed lists transitions (R19.2)", activity["total"] >= 1,
          f"total={activity['total']}")
    check("activity events are PII-safe (no actorId leaked, §9.5/§19)",
          all("actorId" not in item and "actor_id" not in item for item in activity["items"]))

    # SSE probe (§9.4): the stream must open; an event inside the probe window is a bonus.
    try:
        with customer.stream(
            "GET", f"/verifications/{vid_id}/stream", timeout=httpx.Timeout(10.0, read=5.0)
        ) as stream:
            check("SSE tracking stream opens (§9.4)",
                  stream.status_code == 200
                  and "text/event-stream" in stream.headers.get("content-type", ""),
                  f"http {stream.status_code}")
            try:
                for line in stream.iter_lines():
                    if line.strip():
                        check("SSE stream emits an event/heartbeat (§9.4)", True, line[:60])
                        break
            except httpx.ReadTimeout:
                warn("SSE stream stayed quiet within the probe window (§9.4)",
                     "heartbeat cadence exceeds the 5s probe — route itself is up")
    except httpx.HTTPError as exc:
        check("SSE tracking stream opens (§9.4)", False, repr(exc))
