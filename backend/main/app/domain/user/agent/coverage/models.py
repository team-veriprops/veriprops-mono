"""Agent geographic-coverage domain (PRD §3.1 step 4).

The states/LGAs/places an agent will work, with an optional travel radius.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Column, Integer, String

from main.appodus_utils import BaseEntity, BaseQueryDto, Object, InternalPageRequest


# ─── ORM ──────────────────────────────────────────────────────────

class AgentCoverage(BaseEntity):
    __tablename__ = "agent_coverage"

    user_id = Column(String(36), nullable=False, index=True)
    state = Column(String(64), nullable=False)
    lga = Column(String(64), nullable=True)
    place = Column(String(255), nullable=True)
    travel_radius_km = Column(Integer, nullable=True)


# ─── DTOs ─────────────────────────────────────────────────────────

class CreateAgentCoverageDto(Object):
    user_id: str
    state: str
    lga: Optional[str] = None
    place: Optional[str] = None
    travel_radius_km: Optional[int] = None


class UpdateAgentCoverageDto(Object):
    state: Optional[str] = None
    lga: Optional[str] = None
    place: Optional[str] = None
    travel_radius_km: Optional[int] = None


class SearchAgentCoverageDto(InternalPageRequest, BaseQueryDto):
    user_id: Optional[str] = None


class QueryAgentCoverageDto(BaseQueryDto):
    user_id: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None
    place: Optional[str] = None
    travel_radius_km: Optional[int] = None


# ─── API request/response DTOs ────────────────────────────────────

class AgentCoverageInputDto(Object):
    state: str
    lga: Optional[str] = None
    place: Optional[str] = None
    travel_radius_km: Optional[int] = None
