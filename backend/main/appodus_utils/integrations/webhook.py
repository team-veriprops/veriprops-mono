from logging import Logger

from fastapi import APIRouter, Request, HTTPException
from kink import di
from fastapi.responses import JSONResponse
from fastapi import status
from starlette.responses import Response

from main.app.config.settings import settings, IntegratedPlatform
from main.appodus_utils.exception.exceptions import UnauthorizedException
from main.appodus_utils.integrations.factory import WebhookHandlerFactory

logger: Logger = di['logger']

handler_factory: WebhookHandlerFactory = di[WebhookHandlerFactory]

webhook_router = APIRouter(
    prefix=settings.WEBHOOK_PATH,
    tags=["Webhooks"],
    include_in_schema=settings.SHOW_API
)

@webhook_router.get("/{platform}/redirect")
async def handle_redirect(platform: IntegratedPlatform, request: Request, response: Response):
    logger.info(f"redirect, platform={platform}, request={request.query_params}")
    query_params = request.query_params
    headers = dict(request.headers)

    handler = handler_factory.get_handler(platform)

    if handler:
        return await handler.handle_redirect(query_params, headers, response)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": f"platform '{platform}' not supported"})


@webhook_router.get("/{platform}")
async def verify_webhook(platform: IntegratedPlatform, request: Request):
    logger.info(f"Webhook, platform={platform}, request={request.query_params}")
    query_params = request.query_params
    headers = dict(request.headers)

    handler = handler_factory.get_handler(platform)

    if handler:
        return await handler.verify_webhook(query_params, headers)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": f"platform '{platform}' not supported"})


@webhook_router.post("/{platform}")
async def handle_webhook(platform: IntegratedPlatform, request: Request):
    try:
        body = await request.body()
        headers = dict(request.headers)

        provider = handler_factory.get_handler(platform)

        if provider:
            await provider.handle_webhook(body, headers)
            return JSONResponse(
                content={"status": "success"},
                status_code=status.HTTP_200_OK
            )

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": f"platform '{platform}' not supported"})

    except ValueError as e:
        logger.error(f"Webhook processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"error": str(e)})

    except UnauthorizedException as e:
        logger.error(f"Webhook processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": str(e.message)})
    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail={"error": "Internal server error"})
