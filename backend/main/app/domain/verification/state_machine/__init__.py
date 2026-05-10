"""Verification state-machine — thin domain wrapper.

The canonical StateMachine class and all transition tables live in
app.state.machine so they can be consumed by Task and Report
without circular imports. This module re-exports the verification-specific
symbols so existing callers (`from ... state_machine import ...`) are unaffected.
"""
from main.app.state.machine import (  # noqa: F401
    StateMachine,
    VERIFICATION_TRANSITIONS,
    VERIFICATION_TERMINAL,
    verification_state_machine,
)
from main.app.domain.verification.state_machine.derive import derive_status  # noqa: F401

__all__ = [
    "StateMachine",
    "VERIFICATION_TRANSITIONS",
    "VERIFICATION_TERMINAL",
    "verification_state_machine",
    "derive_status",
]
