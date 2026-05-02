from fastapi import APIRouter

from main.app.domain.user.admin_invitation.controller import admin_invitation_router
from main.app.domain.user.agent.controller import agent_router
from main.app.domain.user.auth.controller import auth_router
from main.appodus_utils import RouterUtils

user_router = APIRouter(prefix="/users", tags=["Users"])

RouterUtils.add_routers(user_router, [auth_router, agent_router, admin_invitation_router])