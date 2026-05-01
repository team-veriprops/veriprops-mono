"""Server-side resumable signup draft endpoints."""
from typing import Any, Dict, Optional

from fastapi import APIRouter
from kink import di

from main.app.domain.user.auth.signup_draft.models import SignupDraftDto
from main.app.domain.user.auth.signup_draft.service import SignupDraftService
from main.appodus_utils import Object
from main.appodus_utils.db.models import SuccessResponse

signup_draft_router = APIRouter(prefix="/signup/draft", tags=["Signup Draft"])
signup_draft_service: SignupDraftService = di[SignupDraftService]


class UpsertSignupDraftDto(Object):
    email: str
    step: int = 0
    payload: Dict[str, Any] = {}


@signup_draft_router.put("", response_model=SuccessResponse[SignupDraftDto])
async def upsert_draft(req: UpsertSignupDraftDto):
    dto = await signup_draft_service.upsert(email=req.email, step=req.step, payload=req.payload)
    return SuccessResponse[SignupDraftDto](data=dto)


@signup_draft_router.get("", response_model=SuccessResponse[Optional[SignupDraftDto]])
async def get_draft(email: str):
    return SuccessResponse[Optional[SignupDraftDto]](
        data=await signup_draft_service.get(email),
    )


@signup_draft_router.delete("", response_model=SuccessResponse[bool])
async def discard_draft(email: str):
    await signup_draft_service.discard(email)
    return SuccessResponse[bool](data=True)
