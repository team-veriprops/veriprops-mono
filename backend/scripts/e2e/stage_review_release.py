"""Stage 4 — admin per-task review, release gate, report + branded PDF (S12 §8, S14 §10).

First live coverage of the review cycle: reject one submission → the agent reworks and
resubmits (SUBMITTED→REJECTED→IN_PROGRESS→SUBMITTED) → approve every task → the release
gate blocks until all are approved → release → COMPLETED with the §12.2 notifications and
the §11.1 SYSTEM auto-post, then the customer report + acknowledgement + PDF (§10.1).
"""
from __future__ import annotations

from .harness import Ctx, check
from .stage_execution import ROLE_PAYLOADS

_REWORK_ROLE = "FIELD"  # the role driven through the reject → rework cycle


def run(ctx: Ctx) -> None:
    admin, customer, vid_id = ctx.admin, ctx.customer, ctx.vid_id
    roles = list(ctx.task_ids.keys())

    review = admin.get(f"/admin/review/{vid_id}").json()["data"]
    check("review context lists every submitted task (§8.1)",
          len(review["tasks"]) == len(roles) and review["status"] == "UNDER_REVIEW",
          f"tasks={len(review['tasks'])} status={review['status']}")

    # 1. Reject one submission → rework (§8.2): SUBMITTED→REJECTED, derive → IN_PROGRESS.
    rejected = admin.post(
        f"/admin/review/{vid_id}/tasks/{_REWORK_ROLE}/reject",
        json={"reason": "Occupancy photos are inconclusive — please recapture."},
    ).json()["data"]
    rework_task = next(t for t in rejected["tasks"] if t["role"] == _REWORK_ROLE)
    check("admin rejection sends the task back to rework (§8.2)",
          rework_task["state"] == "REJECTED" and rejected["status"] == "IN_PROGRESS",
          f"task={rework_task['state']} verification={rejected['status']}")

    agent = ctx.agent(_REWORK_ROLE)
    agent_view = next(t for t in agent.get("/agents/tasks").json()["data"]["items"]
                      if t["id"] == ctx.task_ids[_REWORK_ROLE])
    check("agent sees the rejection reason on the task (§7.4)",
          bool(agent_view.get("rejectionReason")), f"reason={agent_view.get('rejectionReason')}")
    check("agent got the TASK_REJECTED notification (§12.2 agent)",
          "TASK_REJECTED" in {n["type"] for n in agent.get("/notifications").json()["data"]["items"]})

    # 2. Agent reworks: REJECTED → IN_PROGRESS (restart) → resubmits (evidence persists).
    restarted = agent.post(f"/agents/tasks/{ctx.task_ids[_REWORK_ROLE]}/start").json()["data"]
    check("agent restarts the rejected task (REJECTED→IN_PROGRESS)",
          restarted["state"] == "IN_PROGRESS")
    resubmitted = agent.post(f"/agents/tasks/{ctx.task_ids[_REWORK_ROLE]}/submit",
                             json={"payload": ROLE_PAYLOADS[_REWORK_ROLE]}).json()["data"]
    check("agent resubmits after rework (§8.2 cycle closes)", resubmitted["state"] == "SUBMITTED")

    # 3. The release gate blocks while any task is not review-approved (§8.3).
    early = admin.post(f"/admin/review/{vid_id}/release", json={"reason": "premature"})
    check("release gate blocks until every task is review-approved (§8.3)",
          early.status_code >= 400, f"http {early.status_code}")

    # 4. Approve every task with a quality score → releasable.
    for role in roles:
        approved = admin.post(f"/admin/review/{vid_id}/tasks/{role}/approve",
                              json={"quality": 92}).json()["data"]
        task = next(t for t in approved["tasks"] if t["role"] == role)
        check(f"admin review-approved the {role} submission (§8.1)",
              task["state"] == "SUBMITTED", f"state={task['state']}")
    gated = admin.get(f"/admin/review/{vid_id}").json()["data"]
    check("review context reports all-approved + releasable (§8.3)",
          gated["allApproved"] is True and gated["releasable"] is True)

    # 5. Release → COMPLETED (§8.3) with §12.2 notifications + §11.1 auto-post.
    rel = admin.post(f"/admin/review/{vid_id}/release", json={"reason": "All checks passed."})
    check("admin release succeeded (UNDER_REVIEW → COMPLETED)", rel.status_code == 200,
          f"http {rel.status_code}")

    types = {n["type"] for n in customer.get("/notifications").json()["data"]["items"]}
    check("customer got a REPORT_READY notification (§12.2)", "REPORT_READY" in types, str(types))
    check("customer got a STATUS_CHANGED notification (§12.2)", "STATUS_CHANGED" in types, str(types))
    unread = customer.get("/notifications/unread").json()["data"]["count"]
    check("customer notification counter is non-zero", unread > 0, f"count={unread}")

    msgs = customer.get(f"/chat/conversations/{ctx.conv_id}/messages").json()["data"]["items"]
    autoposts = [m for m in msgs if m["messageKind"] == "SYSTEM_AUTO"]
    check("status change auto-posted a SYSTEM breadcrumb into the thread (§11.1 / G1)",
          len(autoposts) > 0, f"system messages={len(autoposts)}")

    # 6. Customer report experience (§10): view, one-time acknowledgement, branded PDF.
    report = customer.get(f"/verifications/{vid_id}/report").json()["data"]
    check("customer report is released with a composite trust score (§10)",
          report.get("vid") == ctx.vid and report.get("trustScore") is not None,
          f"score={report.get('trustScore')}")
    acked = customer.post(f"/verifications/{vid_id}/report/acknowledge").json()["data"]
    check("customer acknowledged the report access gate (§10.2)", bool(acked), "")
    pdf = customer.get(f"/verifications/{vid_id}/report/pdf")
    check("branded report PDF downloads (§10.1)",
          pdf.status_code == 200 and pdf.headers.get("content-type", "").startswith("application/pdf")
          and pdf.content[:4] == b"%PDF", f"http {pdf.status_code} bytes={len(pdf.content)}")
