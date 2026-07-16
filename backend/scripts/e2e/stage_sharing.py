"""Stage 6 — public lookup + link/named-recipient sharing (S17 §13).

The fresh verification is COMPLETED by now: public VID lookup stays PRIVATE until the
customer opts in, the public summary exposes the trust BAND (never the number), link and
named shares resolve with the disclaimer gate, and revocation is immediate.
"""
from __future__ import annotations

from .harness import Ctx, check, client


def run(ctx: Ctx) -> None:
    customer, vid_id, vid = ctx.customer, ctx.vid_id, ctx.vid
    public = client()  # unauthenticated

    private_lookup = public.get(f"/public/verify/{vid}").json()["data"]
    check("public lookup is PRIVATE before sharing is enabled (§13.1)",
          private_lookup["state"] == "PRIVATE", f"state={private_lookup['state']}")

    customer.put(f"/verifications/{vid_id}/public-visibility", json={"enabled": True}).raise_for_status()
    summary = public.get(f"/public/verify/{vid}").json()["data"]
    check("public lookup returns the summary once public (§13.1)", summary["state"] == "SHARED")
    check("public summary exposes the trust BAND, never the number (§13.1)",
          bool(summary.get("trustBand")) and "trustScore" not in summary)

    link = customer.post(f"/verifications/{vid_id}/shares",
                         json={"shareType": "LINK_SUMMARY"}).json()["data"]
    link_view = public.get(f"/public/shared/{link['token']}").json()["data"]
    check("a link share resolves to the summary (§13.2)", link_view["state"] == "SHARED"
          and link_view.get("summary") is not None)

    named = customer.post(f"/verifications/{vid_id}/shares",
                          json={"shareType": "NAMED_FULL", "recipientEmail": "friend@example.com"}).json()["data"]
    gated = public.get(f"/public/shared/{named['token']}").json()["data"]
    check("a named share is gated on the disclaimer before the full report (§13.2)",
          gated["requiresAcknowledgement"] is True and gated.get("report") is None)
    acked = public.post(f"/public/shared/{named['token']}/acknowledge").json()["data"]
    check("acknowledging the disclaimer unlocks the full report (§13.2)", acked.get("report") is not None)

    customer.post(f"/verifications/{vid_id}/shares/{link['id']}/revoke").raise_for_status()
    revoked = public.get(f"/public/shared/{link['token']}").json()["data"]
    check("revoking a share invalidates the token immediately (§13.3)",
          revoked["state"] == "NOT_FOUND", f"state={revoked['state']}")
