from fastapi import APIRouter

from main.appodus_utils.config.bootstrap import BaseDiBootstrap # important
from main.app.domain.bank.controller import bank_router

router = APIRouter()
router.include_router(bank_router)
