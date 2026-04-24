import hashlib
import hmac
from logging import Logger

from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from kink import di
from starlette import status

from main.app.config.settings import settings

messagin_router = APIRouter(prefix="/webhooks")

logger: Logger = di['logger']


@messagin_router.get("/whatsapp")
async def verify_whatsapp_webhook(
        request: Request
):
    mode = request.query_params.get('hub.mode')
    challenge = request.query_params.get('hub.challenge')
    token = request.query_params.get('hub.verify_token')

    """Verify WhatsApp webhook endpoint"""
    if mode == "subscribe" and token == settings.WHATSAPP_BUSINESS_WEBHOOK_VERIFY_TOKEN:
        return JSONResponse(content=int(challenge))
    raise HTTPException(status_code=403, detail="Invalid verification token")


@messagin_router.post("/whatsapp")
async def handle_whatsapp_webhook(
        request: Request,
        content_length: int = Header(...),
        x_hub_signature_256: str = Header(...)
):
    if content_length > 1_000_000:
        # To prevent memory allocation attacks
        logger.error(f"Content too long ({content_length})")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Content too long")

    # Validate X-Hub-Signature
    if not (await _validate_signature(request, x_hub_signature_256)):
        logger.error("Invalid message signature")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    logger.info("Message signature checked ok")
    body = await request.json()

    logger.info(f"Request body: {body}")
    # payload = FacebookPageWebhookPayload(**body)

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            for message in change.get("value", {}).get("messages", []):
                # Handle message status updates
                if message.get("status"):
                    pass
                    # await message_repo.update_status(
                    #     external_id=message["id"],
                    #     status=message["status"],
                    #     provider="whatsapp_business"
                    # )

        return {"status": "ok"}

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unhandled object type")


async def _validate_signature(request: Request, signature: str) -> bool:
    """
    Validate the X-Hub-Signature to ensure the request is from Facebook.
    """
    if not signature or not signature.startswith("sha256="):
        return False

    try:
        body = await request.body()
        expected_signature = hmac.new(
            settings.FACEBOOK_APP_SECRET_KEY.encode(), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature.split("=")[1], expected_signature)
    except Exception as e:
        return False
