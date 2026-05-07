"""KYC provider abstraction for agent applications.

A pluggable interface lets us swap concrete BVN/selfie vendors (Mono, Dojah,
Okra) without touching the agent service. PRD Open Q #15 / #16.
"""
from main.app.domain.user.agent.kyc import models  # noqa: F401  — register KycRecord ORM
