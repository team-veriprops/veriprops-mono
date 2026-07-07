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


class ReportRevisionKind(str, enum.Enum):
    """Why a report version was produced (PRD §10.1 / §14) — drives the ``version_label``.

    ``INITIAL`` → v1.0. ``ADMIN_REVISION`` → a minor bump (v1.1). ``RECHECK`` (§14.1) and
    ``TIER_UPGRADE`` (§14.2) → a new major (v2.0 / v3.0). Prior versions move to SUPERSEDED.
    """

    INITIAL = "INITIAL"
    ADMIN_REVISION = "ADMIN_REVISION"
    RECHECK = "RECHECK"
    TIER_UPGRADE = "TIER_UPGRADE"


class ChatMessageState(str, enum.Enum):
    """In-app chat message lifecycle (PRD §4.7, §11.2).

    Every message is scanned at send time. Unflagged messages take the fast lane
    straight to ``DELIVERED``; a flagged message is ``HELD`` for admin review, then
    either ``DELIVERED`` (approved) or ``BLOCKED`` (rejected). ``DELIVERED`` and
    ``BLOCKED`` are terminal.
    """

    PENDING_SCAN = "PENDING_SCAN"
    HELD = "HELD"
    DELIVERED = "DELIVERED"
    BLOCKED = "BLOCKED"


class ErasureRequestState(str, enum.Enum):
    """NDPA data-erasure request lifecycle (PRD §18.1, §19.1).

    A data subject (or an admin on their behalf) opens a request as ``PENDING``.
    An admin with ``MANAGE_COMPLIANCE`` either ``REJECTED`` it or moves it to
    ``APPROVED``; approval is then carried out by the irreversible pseudonymisation
    step, landing on ``EXECUTED``. ``EXECUTED`` and ``REJECTED`` are terminal.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class VerificationTier(str, enum.Enum):
    """Verification tier (PRD §1.4)."""

    BASIC = "BASIC"
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"


class ShareType(str, enum.Enum):
    """How a released report is shared beyond the owning customer (PRD §13.2).

    ``LINK_SUMMARY`` — anyone holding the tokenised link sees the public *summary*.
    ``NAMED_FULL`` — a specific email recipient sees the *full* report, after a one-time
    disclaimer acknowledgement. Both are time-limited and revocable. (Private = no share
    row; Public = the verification's ``public_lookup_enabled`` flag on the VID lookup.)
    """

    LINK_SUMMARY = "LINK_SUMMARY"
    NAMED_FULL = "NAMED_FULL"


class AgentRole(str, enum.Enum):
    """Agent / task role (PRD §1.4, §7.3)."""

    REGISTRY = "REGISTRY"
    FIELD = "FIELD"
    SURVEYOR = "SURVEYOR"
    LAWYER = "LAWYER"
