"""Canonical status / role enums shared across the verification lifecycle.

Single source of truth for the string values that flow through the state
machines (``machine.py``), the derivation owner (``derive.py``), the
task-dependency config (``dependencies.py``), and — later — the rebuilt
verification/task/report domains and their API DTOs.

PRD references: §2.1 (Verification), §2.2 (Task), §2.3 (Report), §1.4 (tiers/roles).
"""
from __future__ import annotations

import enum


class VerificationStatus(str, enum.Enum):
    """Global verification status (PRD §2.1). Derived by ``derive_status``."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    IN_PROGRESS = "IN_PROGRESS"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"
    DISPUTED = "DISPUTED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


class TaskState(str, enum.Enum):
    """Per-role task state (PRD §2.2)."""

    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"


class ReportState(str, enum.Enum):
    """Report state (PRD §2.3)."""

    DRAFT = "DRAFT"
    RELEASED = "RELEASED"
    SUPERSEDED = "SUPERSEDED"


class VerificationTier(str, enum.Enum):
    """Verification tier (PRD §1.4)."""

    BASIC = "BASIC"
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"


class AgentRole(str, enum.Enum):
    """Agent / task role (PRD §1.4, §7.3)."""

    REGISTRY = "REGISTRY"
    FIELD = "FIELD"
    SURVEYOR = "SURVEYOR"
    LAWYER = "LAWYER"
