"""Communication layer (PRD §11, §4.7).

Structured, admin-mediated, fraud-scanned in-app chat — never direct customer↔agent
(§4.6 communication boundaries). One thread per verification per channel plus a general
support thread; every message runs a synchronous send-time fraud scan (§4.7): unflagged
messages take the fast lane straight to DELIVERED, a flagged message is HELD for admin
approve/reject. Delivery is over the SSE transport (§4.9); sends are ordinary HTTP POST.

Child domains (one entity each): ``conversation`` (thread), ``conversation_participant``
(per-user read state — backs the Chat counter), ``chat_message`` (the messages + their
§4.7 state machine). ``fraud_scan`` is the pure, deterministic scanner they share.
"""
