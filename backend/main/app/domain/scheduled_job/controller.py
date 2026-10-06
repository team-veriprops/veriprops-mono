"""The external sweep trigger: `POST /internal/sweeps/tick` (D12 follow-up).

Every deployed environment is serverless, where the in-process scheduler cannot be trusted to
fire, so a Cloudflare Cron Worker (`infra/cloudflare/sweep-cron/`) calls this every minute and
the tick runs whatever sweeps are due. The caller is a machine, not a user: it carries no
session, and is authorised by `SWEEP_TRIGGER_SECRET` in the `SWEEP_TRIGGER_HEADER` header.

Without a configured secret the endpoint answers 404 — disabled, never open. Production and
staging refuse to boot without one (`Settings._enforce_sweep_trigger_in_deployed_envs`).
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Request

from main.app.config.settings import settings
from main.app.domain.scheduled_job.models import SweepTickResultDto
from main.appodus_utils.config.settings import is_configured_secret
from main.appodus_utils.db.models import SuccessResponse
from main.appodus_utils.exception.exceptions import ResourceNotFoundException, UnauthorizedException

sweep_router = APIRouter(prefix="/internal/sweeps", tags=["Sweeps"])


def _authorize_sweep_trigger(request: Request) -> None:
    configured = settings.SWEEP_TRIGGER_SECRET
    if not is_configured_secret(configured):
        raise ResourceNotFoundException(resource="sweep tick")
    supplied = request.headers.get(settings.SWEEP_TRIGGER_HEADER, "")
    if not secrets.compare_digest(supplied.encode(), configured.strip().encode()):
        raise UnauthorizedException("The sweep trigger secret is missing or wrong.")


@sweep_router.post("/tick", response_model=SuccessResponse[SweepTickResultDto])
async def tick(request: Request):
    """Run every sweep that is due, in registry order, and report what each did."""
    _authorize_sweep_trigger(request)
    # Resolved here, not at import: the job registry imports every sweep task, and the task
    # modules import domain services, which load this package's router — a cycle at import.
    from main.app.jobs import tick
    return SuccessResponse[SweepTickResultDto](data=await tick.run_sweep_tick())
