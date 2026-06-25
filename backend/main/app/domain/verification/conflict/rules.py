"""Conflict detection rules — D15 provisional set (S29).

Each rule examines the submitted task payloads and returns a ConflictFlagDto if
a contradiction is detected, or None if the data is consistent.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Optional

from main.app.domain.verification.conflict.models import (
    ConflictFlagDto,
    ConflictSeverity,
    ConflictStatus,
)
from main.app.domain.verification.task.models import Task, TaskRole
from main.appodus_utils import Utils


class BaseConflictRule(ABC):
    rule_id: str
    severity: ConflictSeverity = ConflictSeverity.BLOCKER

    @abstractmethod
    def check(self, tasks: List[Task], verification_id: str) -> Optional[ConflictFlagDto]:
        ...

    def _payload(self, tasks: List[Task], role: TaskRole) -> dict:
        import json
        for t in tasks:
            if t.role == role.value:
                try:
                    return json.loads(t.draft_payload or "{}")
                except (ValueError, TypeError):
                    return {}
        return {}

    def _flag(self, verification_id: str, description: str) -> ConflictFlagDto:
        from datetime import datetime, timezone
        return ConflictFlagDto(
            id=str(Utils.generate_uuid()),
            verification_id=verification_id,
            rule_id=self.rule_id,
            severity=self.severity,
            description=description,
            status=ConflictStatus.OPEN,
            date_created=datetime.now(timezone.utc),
        )


class OccupancyMismatchRule(BaseConflictRule):
    """Rule 1: Field agent's occupancy_status contradicts Registry registered_occupancy."""
    rule_id = "OCCUPANCY_MISMATCH"

    CONTRADICTION: dict[str, set] = {
        "VACANT": {"OCCUPIED", "IN_USE"},
        "OCCUPIED": {"VACANT", "UNOCCUPIED"},
        "IN_USE": {"VACANT"},
    }

    def check(self, tasks: List[Task], verification_id: str) -> Optional[ConflictFlagDto]:
        field_p = self._payload(tasks, TaskRole.FIELD)
        registry_p = self._payload(tasks, TaskRole.REGISTRY)
        field_occ = str(field_p.get("occupancy_status", "")).upper()
        reg_occ = str(registry_p.get("registered_occupancy", "")).upper()
        if not field_occ or not reg_occ:
            return None
        if reg_occ in self.CONTRADICTION.get(field_occ, set()):
            return self._flag(
                verification_id,
                f"Occupancy mismatch: Field agent reports '{field_occ}', "
                f"Registry records show '{reg_occ}'.",
            )
        return None


class BoundaryDivergenceRule(BaseConflictRule):
    """Rule 2: Surveyor boundary_coords diverge >5m from Registry survey_plan_coords."""
    rule_id = "BOUNDARY_DIVERGENCE"
    _THRESHOLD_METRES = 5.0

    def check(self, tasks: List[Task], verification_id: str) -> Optional[ConflictFlagDto]:
        surveyor_p = self._payload(tasks, TaskRole.SURVEYOR)
        registry_p = self._payload(tasks, TaskRole.REGISTRY)
        s_coords = surveyor_p.get("boundary_coords")
        r_coords = registry_p.get("survey_plan_coords")
        if not s_coords or not r_coords:
            return None
        try:
            s_lat, s_lng = float(s_coords.get("lat", 0)), float(s_coords.get("lng", 0))
            r_lat, r_lng = float(r_coords.get("lat", 0)), float(r_coords.get("lng", 0))
        except (TypeError, AttributeError, ValueError):
            return None
        dist = self._haversine_metres(s_lat, s_lng, r_lat, r_lng)
        if dist > self._THRESHOLD_METRES:
            return self._flag(
                verification_id,
                f"Boundary divergence of {dist:.1f}m exceeds {self._THRESHOLD_METRES}m threshold. "
                f"Surveyor: ({s_lat:.6f}, {s_lng:.6f}), Registry: ({r_lat:.6f}, {r_lng:.6f}).",
            )
        return None

    @staticmethod
    def _haversine_metres(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lng2 - lng1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class AuthenticityConflictRule(BaseConflictRule):
    """Rule 3: Lawyer flags document as FORGED but Registry assessed it AUTHENTIC."""
    rule_id = "AUTHENTICITY_CONFLICT"

    def check(self, tasks: List[Task], verification_id: str) -> Optional[ConflictFlagDto]:
        lawyer_p = self._payload(tasks, TaskRole.LAWYER)
        registry_p = self._payload(tasks, TaskRole.REGISTRY)
        lawyer_auth = str(lawyer_p.get("document_authenticity", "")).upper()
        registry_auth = str(registry_p.get("title_doc_assessment", "")).upper()
        if lawyer_auth == "FORGED" and registry_auth == "AUTHENTIC":
            return self._flag(
                verification_id,
                "Authenticity conflict: Lawyer flagged documents as FORGED but "
                "Registry assessment recorded them as AUTHENTIC.",
            )
        return None


class OwnerNameMismatchRule(BaseConflictRule):
    """Rule 4: Last entry in Registry ownership_chain doesn't match seller_name on the property."""
    rule_id = "OWNER_NAME_MISMATCH"
    severity = ConflictSeverity.WARNING

    def check(self, tasks: List[Task], verification_id: str) -> Optional[ConflictFlagDto]:
        registry_p = self._payload(tasks, TaskRole.REGISTRY)
        ownership_chain = registry_p.get("ownership_chain")
        if not ownership_chain or not isinstance(ownership_chain, list) or len(ownership_chain) == 0:
            return None
        last_owner = str(
            ownership_chain[-1].get("name", "") if isinstance(ownership_chain[-1], dict) else "").strip().lower()
        # seller_name comes from the verification's property data, passed via the registry payload
        seller_name = str(registry_p.get("seller_name", "")).strip().lower()
        if not last_owner or not seller_name:
            return None
        if last_owner != seller_name:
            return self._flag(
                verification_id,
                f"Owner name mismatch: Registry chain ends with '{last_owner}' "
                f"but seller name on record is '{seller_name}'.",
            )
        return None


ALL_RULES: List[BaseConflictRule] = [
    OccupancyMismatchRule(),
    BoundaryDivergenceRule(),
    AuthenticityConflictRule(),
    OwnerNameMismatchRule(),
]


def run_all_rules(tasks: List[Task], verification_id: str) -> List[ConflictFlagDto]:
    flags: List[ConflictFlagDto] = []
    for rule in ALL_RULES:
        try:
            flag = rule.check(tasks, verification_id)
            if flag is not None:
                flags.append(flag)
        except Exception:  # noqa: BLE001
            pass  # defensive: rule failures must never block the review flow
    return flags
