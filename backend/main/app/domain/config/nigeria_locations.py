"""Canonical Nigerian states reference (PRD §16.1, D33).

The backend owns the states canon so coverage validation + assignment matching and the
frontend coverage picker / map all agree on one source of truth. ``code`` matches the SVG
map region ids on the frontend. LGA granularity stays a free-text convenience on coverage
rows; the state is the matching-critical field.
"""
from __future__ import annotations

from typing import List

from main.appodus_utils import Object

# (code, label). The 36 states + FCT. Codes are lowercase-hyphenated, matching the map ids.
_STATES: tuple[tuple[str, str], ...] = (
    ("abia", "Abia"), ("adamawa", "Adamawa"), ("akwa-ibom", "Akwa Ibom"), ("anambra", "Anambra"),
    ("bauchi", "Bauchi"), ("bayelsa", "Bayelsa"), ("benue", "Benue"), ("borno", "Borno"),
    ("cross-river", "Cross River"), ("delta", "Delta"), ("ebonyi", "Ebonyi"), ("edo", "Edo"),
    ("ekiti", "Ekiti"), ("enugu", "Enugu"), ("fct", "FCT (Abuja)"), ("gombe", "Gombe"),
    ("imo", "Imo"), ("jigawa", "Jigawa"), ("kaduna", "Kaduna"), ("kano", "Kano"),
    ("katsina", "Katsina"), ("kebbi", "Kebbi"), ("kogi", "Kogi"), ("kwara", "Kwara"),
    ("lagos", "Lagos"), ("nasarawa", "Nasarawa"), ("niger", "Niger"), ("ogun", "Ogun"),
    ("ondo", "Ondo"), ("osun", "Osun"), ("oyo", "Oyo"), ("plateau", "Plateau"),
    ("rivers", "Rivers"), ("sokoto", "Sokoto"), ("taraba", "Taraba"), ("yobe", "Yobe"),
    ("zamfara", "Zamfara"),
)

# Valid state codes for coverage validation (§16.1).
STATE_CODES = frozenset(code for code, _ in _STATES)


class NigerianStateDto(Object):
    code: str
    label: str


class NigeriaLocationsDto(Object):
    states: List[NigerianStateDto]


def nigeria_locations() -> NigeriaLocationsDto:
    return NigeriaLocationsDto(
        states=[NigerianStateDto(code=code, label=label) for code, label in _STATES]
    )


def is_valid_state(code: str) -> bool:
    return (code or "").strip().lower() in STATE_CODES
