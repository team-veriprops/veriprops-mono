"""Agent application & onboarding domain.

PRD §2 (Actors), Phase 3 (Agent Onboarding & KYC). An applicant submits a
multi-step application; on admin approval, AGENT persona is appended to the
user record.
"""
from main.app.domain.user.agent import models  # noqa: F401  — register ORM
from main.app.domain.user.agent.kyc import factory as kyc_factory  # noqa: F401
