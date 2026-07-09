"""Customer tracking & evidence layer (PRD §9).

Orchestration-only sub-package of the verification domain (no ORM entity of its own —
like the admin control panel). Projects the verification aggregate into the customer's
live tracking dashboard and tamper-evident evidence feed, delivered over the §4.9 SSE
transport with a 60-second polling fallback that shares one snapshot shape.

Enforces two customer-facing guardrails at the API layer:
- **First-name-only** agent identity (§4.9/§9.5) — never last name / email / phone.
- **Interim reassurance** (§9.3) — a task's positive milestone (and its evidence) is
  surfaced only after admin review-approval, so a risk-bearing finding is never leaked
  before it is delivered with context.
"""
