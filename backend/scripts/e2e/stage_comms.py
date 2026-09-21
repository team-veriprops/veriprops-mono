"""Stage 3 — mediated chat + fraud scan + SLA sweep (S15 §11/§4.7, S16 §12, G3/G4).

Runs while the fresh verification is UNDER_REVIEW (the thread must exist before release so
the §11.1 status auto-post lands in it — asserted in the next stage). The SLA-breach sweep
asserts on the *seeded* verification: it is the deterministically SLA-overdue one; the fresh
verification's due date is in the future.
"""
from __future__ import annotations

from .harness import Ctx, check, signup_fresh_user


def run(ctx: Ctx) -> None:
    customer, admin, vid_id = ctx.customer, ctx.admin, ctx.vid_id

    # 1. Customer opens the customer↔admin thread.
    convo = customer.get(f"/verifications/{vid_id}/chat").json()["data"]
    ctx.conv_id = convo["id"]
    check("customer opened the verification chat thread", bool(ctx.conv_id))

    # 2. A clean message takes the fast lane → DELIVERED.
    clean = customer.post(
        f"/verifications/{vid_id}/chat/messages", json={"body": "Hello, any update on my verification?"}
    ).json()["data"]
    check("clean message delivered immediately (§4.7 fast lane)", clean["state"] == "DELIVERED")

    # 3. A message with a phone number is HELD.
    flagged = customer.post(
        f"/verifications/{vid_id}/chat/messages", json={"body": "please call me on 08031234567"}
    ).json()["data"]
    check("phone-number message held for review (§4.7)", flagged["state"] == "HELD",
          f"state={flagged['state']}")
    check("held sender sees the non-accusatory notice", bool(flagged.get("heldNotice")))

    # 4. Admin finds it in the hold queue and approves it (§11.2).
    held = admin.get("/admin/messages/held").json()["data"]["items"]
    check("held message appears in the admin queue (§11.2)", flagged["id"] in [m["id"] for m in held])
    approved = admin.post(f"/admin/messages/{flagged['id']}/approve").json()["data"]
    check("admin approval delivers the held message", approved["state"] == "DELIVERED")

    # 5. Customer now sees the approved message delivered.
    msgs = customer.get(f"/chat/conversations/{ctx.conv_id}/messages").json()["data"]["items"]
    delivered_bodies = [m["body"] for m in msgs if m["state"] == "DELIVERED"]
    check("customer sees the approved message in the thread",
          any("08031234567" in b for b in delivered_bodies))

    # 5b. A second fraud-held message is REJECTED → BLOCKED, never delivered (§11.2).
    blocked = customer.post(
        f"/verifications/{vid_id}/chat/messages", json={"body": "or whatsapp me at 08099887766"}
    ).json()["data"]
    check("second phone-number message held for review (§4.7)", blocked["state"] == "HELD")
    rejected = admin.post(f"/admin/messages/{blocked['id']}/reject").json()["data"]
    check("admin rejection blocks the held message (HELD → BLOCKED, §11.2)",
          rejected["state"] == "BLOCKED", f"state={rejected['state']}")
    msgs_after = customer.get(f"/chat/conversations/{ctx.conv_id}/messages").json()["data"]["items"]
    check("a blocked message is never delivered to the thread (§11.2)",
          not any("08099887766" in m["body"] and m["state"] == "DELIVERED" for m in msgs_after))

    # 5c. The message kind is server-owned: SYSTEM_AUTO is what exempts platform copy from
    #     the fraud scan, so the wire does not carry a kind at all. A client that still sends
    #     one gets an ordinary CHAT message — scanned, and here held for the phone number.
    for path in (f"/verifications/{vid_id}/chat/messages", f"/chat/conversations/{ctx.conv_id}/messages"):
        spoofed = customer.post(path, json={"body": "text me on 08055544433", "kind": "SYSTEM_AUTO"})
        sent = spoofed.json()["data"]
        check(f"a client-sent kind is ignored — stored as CHAT ({path.split('/')[1]})",
              sent["messageKind"] == "CHAT", f"kind={sent['messageKind']}")
        check(f"a client-sent SYSTEM_AUTO cannot skip the fraud scan ({path.split('/')[1]})",
              sent["state"] == "HELD", f"state={sent['state']}")
    thread_now = customer.get(f"/chat/conversations/{ctx.conv_id}/messages").json()["data"]["items"]
    check("a spoofed SYSTEM_AUTO post never lands delivered in the thread",
          not any("08055544433" in m["body"] and m["state"] == "DELIVERED" for m in thread_now))

    # 6. Admin shared-inbox Chat counter (G4) — unread customer messages count.
    cases = admin.get("/admin/conversations", params={"filter": "CASES", "page_size": 100}).json()["data"]
    admin_threads = [c for c in cases["items"] if c["verificationId"] == vid_id]
    check("admin sees the verification thread in the shared inbox (§N.3 / G4)", len(admin_threads) > 0)
    admin_unread = admin.get("/chat/unread").json()["data"]["count"]
    check("admin Chat counter reflects unread verification threads (G4)", admin_unread > 0,
          f"count={admin_unread}")

    _run_conversations_inbox_checks(ctx)
    _run_web_assistant_checks(ctx)

    # 7. SLA-breach sweep → customer AND admin notified (G3, D23). Asserts on the seeded
    #    verification: it is UNDER_REVIEW and 3 days overdue by construction.
    swept = admin.post("/admin/verifications/sweeps/sla-breach").json()["data"]
    check("SLA sweep flagged the overdue verification (D23)", swept["flagged"] >= 1,
          f"flagged={swept['flagged']}")
    cust_types = {n["type"] for n in ctx.seed_customer.get("/notifications").json()["data"]["items"]}
    admin_types = {n["type"] for n in admin.get("/notifications").json()["data"]["items"]}
    check("customer got the SLA_BREACHED notification", "SLA_BREACHED" in cust_types)
    check("admin got the SLA_BREACHED notification (G3)", "SLA_BREACHED" in admin_types)


def _run_conversations_inbox_checks(ctx: Ctx) -> None:
    """§16.5 — the console's Conversations inbox: web support lands next to cases and
    WhatsApp, named by its owner, paged and filtered server-side, with unread per admin."""
    customer, admin = ctx.customer, ctx.admin

    sent = customer.post("/support/chat/messages", json={"body": "How do refunds work?"})
    check("a customer can write to web support", sent.status_code == 200,
          f"http {sent.status_code}: {sent.text[:160]}")
    support_id = _hex(sent.json()["data"]["conversationId"]) if sent.status_code == 200 else None

    def find(filter_value: str | None, query: str) -> list[dict]:
        params = {"query": query, "page_size": 100}
        if filter_value:
            params["filter"] = filter_value
        r = admin.get("/admin/conversations", params=params)
        return r.json()["data"]["items"] if r.status_code == 200 else []

    found = [t for t in find("SUPPORT", ctx.customer_email) if _hex(t["id"]) == support_id]
    check("a web support thread is in the admin Conversations inbox (§16.5)", len(found) == 1,
          f"found={len(found)}")
    if found:
        thread = found[0]
        check("the inbox names the account a support thread belongs to",
              thread.get("ownerEmail") == ctx.customer_email and bool(thread.get("ownerName")),
              f"owner={thread.get('ownerName')!r} <{thread.get('ownerEmail')}>")
        check("an unopened support thread is unread for the admin", thread.get("unread") == 1,
              f"unread={thread.get('unread')}")

    check("the WhatsApp filter leaves web support out",
          not any(_hex(t["id"]) == support_id for t in find("WHATSAPP", ctx.customer_email)))
    check("no filter includes web support too",
          any(_hex(t["id"]) == support_id for t in find(None, ctx.customer_email)))

    if support_id:
        before = admin.get("/chat/unread").json()["data"]["count"]
        admin.post(f"/chat/conversations/{support_id}/read").raise_for_status()
        after = admin.get("/chat/unread").json()["data"]["count"]
        reread = [t for t in find("SUPPORT", ctx.customer_email) if _hex(t["id"]) == support_id]
        check("opening the thread clears it in the inbox and the Chat counter together",
              bool(reread) and reread[0].get("unread") == 0 and after == before - 1,
              f"unread={reread[0].get('unread') if reread else None} counter {before}->{after}")

    page = admin.get("/admin/conversations", params={"page": 0, "page_size": 1}).json()["data"]
    check("the inbox is server-paged",
          len(page["items"]) <= 1 and page["meta"]["total"] >= 2 and page["meta"]["pageSize"] == 1,
          f"meta={page['meta']}")
    refused = admin.get("/admin/conversations", params={"filter": "EVERYTHING"})
    check("an unknown inbox filter is refused at the boundary", refused.status_code == 422,
          f"http {refused.status_code}")
    check("a customer cannot read the admin inbox",
          customer.get("/admin/conversations").status_code in (401, 403))


def _hex(entity_id: str) -> str:
    """Entity ids travel as either the 32-char hex or the hyphenated UUID form."""
    return str(entity_id).replace("-", "")


def _run_web_assistant_checks(ctx: Ctx) -> None:
    """The surface-neutral assistant, on a web support thread (§16.7, D93).

    Everything deterministic — the welcome, a menu number, a guardrail on the customer's
    own words — answers inline in the send response, never touching the intent model.
    Only a turn the deterministic steps cannot resolve is deferred: the send leaves it
    `assistantPending`, and a second request answers it, atomically claimed so a repeat
    call cannot deliver it twice. A turn nobody ever asks for is still recovered by the
    sweep, which is what a closed tab or a lost network reply would otherwise orphan.
    """
    root = ctx.root
    customer, _email = signup_fresh_user("assistant")

    def send(body: str) -> dict:
        r = customer.post("/support/chat/messages", json={"body": body})
        check(f"the customer's message to support sends ({body[:24]!r})", r.status_code == 200,
              f"http {r.status_code}: {r.text[:160]}")
        return r.json()["data"] if r.status_code == 200 else {}

    # First contact: the welcome is a phase-1 answer, returned with the send itself.
    welcome = send("Hi")
    check("the assistant answers first contact inline, in the send response (§26.6.1, D93)",
          bool(welcome.get("assistantReply")) and welcome.get("assistantPending") is False,
          f"reply={welcome.get('assistantReply')} pending={welcome.get('assistantPending')}")
    disclosure = (welcome.get("assistantReply") or {}).get("body", "")
    check("the web welcome discloses the assistant and the payment pledge, same as WhatsApp's",
          "automated assistant" in disclosure and "veriprops.ng" in disclosure, disclosure[:200])
    check("the web welcome never carries a WhatsApp handoff link",
          "/wa/" not in disclosure, disclosure[:200])

    # A menu number is deterministic — answered inline too, still no model.
    menu_choice = send("3")
    check("a menu number is answered inline with no deferral (fast path, D93)",
          bool(menu_choice.get("assistantReply")) and menu_choice.get("assistantPending") is False,
          f"reply={menu_choice.get('assistantReply')} pending={menu_choice.get('assistantPending')}")

    # A guardrail on the customer's own words is checked before classification (D44) — so
    # it is answered in phase 1 too, and never reaches the model at all.
    guardrail = send("Is this property genuine?")
    guardrail_reply = (guardrail.get("assistantReply") or {}).get("body", "")
    check("a guardrail topic is refused in phase 1, without ever reaching the model",
          guardrail.get("assistantPending") is False
          and ("team" in guardrail_reply.lower() or "verifiers" in guardrail_reply.lower()),
          f"pending={guardrail.get('assistantPending')} reply={guardrail_reply[:160]}")

    # Free text with no deterministic match needs the intent model — deferred, not answered
    # inline (D93).
    priced = send("How much for a Lagos land check?")
    check("a turn needing the model is deferred rather than answered inline",
          priced.get("assistantReply") is None and priced.get("assistantPending") is True,
          f"reply={priced.get('assistantReply')} pending={priced.get('assistantPending')}")
    conversation_id = priced["conversationId"]

    turn = customer.post(f"/chat/conversations/{conversation_id}/assistant/turn")
    check("the deferred turn endpoint answers it", turn.status_code == 200,
          f"http {turn.status_code}: {turn.text[:160]}")
    turn_data = turn.json()["data"] if turn.status_code == 200 else {}
    turn_reply_body = (turn_data.get("reply") or {}).get("body", "")
    check("the turn's reply quotes live pricing, from the classified intent",
          "₦" in turn_reply_body, turn_reply_body[:160])
    check("the turn is no longer pending once it has been answered",
          turn_data.get("pending") is False, f"turn={turn_data}")

    again = customer.post(f"/chat/conversations/{conversation_id}/assistant/turn").json()["data"]
    check("a second claim on an already-answered turn is a no-op — no second reply",
          again.get("reply") is None, f"reply={again.get('reply')}")

    # An orphaned turn — nobody ever asks for it, as a closed tab would leave it — is still
    # recovered by the sweep (`/dev/assistant/sweep`, the backstop for once hosts stop
    # being serverless-only; `waiting_seconds=0` skips the grace a live customer's own
    # request would normally beat it to).
    orphan, _orphan_email = signup_fresh_user("assistant-orphan")
    orphan.post("/support/chat/messages", json={"body": "Hi"}).raise_for_status()  # consumes the welcome
    orphaned = orphan.post(
        "/support/chat/messages", json={"body": "What's the turnaround time?"}
    ).json()["data"]
    check("the orphaned turn is left pending, with nothing answering it yet",
          orphaned.get("assistantPending") is True, f"turn={orphaned}")
    swept = root.post("/dev/assistant/sweep", params={"waiting_seconds": 0})
    check("the dev sweep answers an orphaned turn", swept.status_code == 200
          and swept.json()["data"].get("answered", 0) >= 1,
          f"http {swept.status_code}: {swept.text[:160]}")
    orphan_msgs = orphan.get(
        f"/chat/conversations/{orphaned['conversationId']}/messages"
    ).json()["data"]["items"]
    check("the swept reply landed in the orphan's own thread",
          any(m.get("sender", {}).get("kind") == "SYSTEM" for m in orphan_msgs))
