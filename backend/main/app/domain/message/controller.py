from typing import List

from fastapi import APIRouter, Depends, UploadFile, BackgroundTasks
from libre_fastapi_jwt import AuthJWT
from kink import di

from main.appodus_utils import Page
from main.app.domain.user.models import KYCAgent
from main.app.domain.message.service import MessageService
from main.app.domain.message.models import QueryMessageDto, UpsertMessageDto, \
    SearchMessageDto

message_router = APIRouter(prefix="/messages")

message_service = di[MessageService]


@message_router.put("/")
async def message_update(
        update_dto: UpsertMessageDto,
        authorizer: AuthJWT = Depends(),
) -> QueryMessageDto:
    return await message_service.update_message(update_dto, authorizer)


@message_router.put("/active-user/picture")
async def message_update_active_user_picture(
        message_picture: UploadFile,
        background_tasks: BackgroundTasks  = None,
        authorizer: AuthJWT = Depends(),
) -> bool:
    return await message_service.update_active_user_picture(message_picture, authorizer, background_tasks)


@message_router.put("/active-user/selfie")
async def message_update_active_user_selfie(
        selfie_picture: UploadFile,
        background_tasks: BackgroundTasks  = None,
        authorizer: AuthJWT = Depends(),
) -> bool:
    return await message_service.update_active_user_selfie(selfie_picture, authorizer, background_tasks)


@message_router.put("/active-user/bvn")
async def message_update_active_user_bvn(
        bvn: str,
        authorizer: AuthJWT = Depends(),
) -> bool:
    return await message_service.update_active_user_bvn(bvn, authorizer)


@message_router.get("/search")
async def get_message_page(
        search_dto: SearchMessageDto
) -> Page[QueryMessageDto]:
    return await message_service.get_message_page(search_dto)


@message_router.get("/{message_id}")
async def get_message(message_id: str) -> QueryMessageDto:
    return await message_service.get_message(message_id)


@message_router.get("/{message_id}/kyc-pending")
async def get_message_kyc_pending(message_id: str) -> List[KYCAgent]:
    return await message_service.get_message_kyc_pending(message_id)

#
# @message_router.get("/{message_id}/public-message")
# async def get_public_message(message_id: str) -> QueryMessagePublicDto:
#     return await message_service.get_public_message(message_id)


@message_router.get("/active-user")
async def get_message_for_active_user(authorizer: AuthJWT = Depends(), ) -> QueryMessageDto:
    return await message_service.get_message_for_active_user(authorizer)
