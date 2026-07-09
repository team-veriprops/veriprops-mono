"""Compliance parent domain (PRD §19) — audit & compliance maturity.

Groups the compliance-facing sub-domains. Today: ``erasure`` (NDPA data-erasure
workflow + PII pseudonymisation, §4.11). The audit-log read/export surface itself
lives in ``app/domain/audit`` (a low-level, widely-imported domain).
"""
from main.app.domain.compliance import erasure  # noqa: F401
