"""Verification domain — PRD Phase 5+ (verification lifecycle).

Holds the Verification aggregate plus its child packages:
- property/        Property entity (submitted by customer).
- pricing/         Tier pricing + currency conversion + 24-hr price lock.
- state_machine/   Forward-only state validator (PRD §0.2).
- parser/          Listing-URL scraper (R5.2).
- admin/           Admin control panel (Phase 6 S18).
- task/            Task lifecycle (Phase 6-7 S19+).
- escalation/      Agent issue escalation (Phase 7 S27).
"""
from main.app.domain.verification import models  # noqa: F401
from main.app.domain.verification.property import models as property_models  # noqa: F401
from main.app.domain.verification.parser import models as parser_models  # noqa: F401
from main.app.domain.verification.admin import models as admin_models  # noqa: F401
from main.app.domain.verification.task import models as task_models  # noqa: F401
from main.app.domain.verification.escalation import models as escalation_models  # noqa: F401
