"""Verification domain — PRD Phase 5+ (verification lifecycle).

Holds the Verification aggregate plus its child packages:
- property/        Property entity (submitted by customer).
- pricing/         Tier pricing + currency conversion + 24-hr price lock.
- state_machine/   Forward-only state validator (PRD §0.2).
"""
from main.app.domain.verification import models  # noqa: F401
from main.app.domain.verification.property import models as property_models  # noqa: F401
