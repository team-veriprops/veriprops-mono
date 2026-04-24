import os
from logging import Logger

from main.appodus_utils import Utils

from main.appodus_utils.common.client_utils import ClientUtils
from main.app.domain.client.models import ClientAccessRuleDto
from main.app.domain.client.service import ClientService
from main.appodus_utils.exception.exceptions import ForbiddenException
from kink import di
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

client_service: ClientService = di[ClientService]
logger: Logger = di['logger']

ENVIRONMENT: str = os.getenv('ENVIRONMENT', "Environment.DEVELOPMENT")
ALLOW_AUTH_BYPASS: bool =  Utils.get_bool_from_env(env_key="ALLOW_AUTH_BYPASS", default=False)
class ClientAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):


        path = request.url.path

        # --- Skip auth for OpenAPI/docs routes ---
        if path.startswith("/docs") or path.startswith("/redoc") or path == "/openapi.json":
            return await call_next(request)

        # --- Skip auth for test bypass only in non-production ---
        if ALLOW_AUTH_BYPASS:
            if (
                    ENVIRONMENT in ["Environment.LOCAL", "Environment.DEVELOPMENT", "Environment.TEST", "Environment.STAGING"]
            ):
                logger.warning(f"[CLIENT AUTH BYPASS] Skipping client auth for path={request.url.path}, "
                               f"ip={ClientUtils.get_client_ip(request)}, headers={dict(request.headers)}")
                return await call_next(request)
            else:
                raise ForbiddenException("[CLIENT AUTH BYPASS] not allowed in production")

        
        client_id = request.headers.get("x-client-id")
        client_ip = ClientUtils.get_client_ip(request)
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        logger.debug(f"Incoming request - client_id={client_id}, ip={client_ip}, origin={origin}, referer={referer}, path={request.url.path}")

        # --- Client ID validation ---
        if not client_id or not await client_service.client_exists(client_id):
            logger.warning(f"Access denied - Missing or invalid client_id: {client_id}")
            raise ForbiddenException(message="Missing or invalid API key")

        # --- Access rules lookup ---
        access_rules: ClientAccessRuleDto = await client_service.get_client_access_rules(client_id)
        logger.debug(f"Access rules loaded for client_id={client_id}: {access_rules.model_dump()}")

        # --- IP Check ---
        if not ClientUtils.is_ip_allowed(client_ip, access_rules.allowed_ips):
            logger.warning(f"Access denied - IP {client_ip} not allowed for client_id={client_id}")
            raise ForbiddenException(message=f"IP {client_ip} not allowed")

        # --- Origin / Referer Check ---
        origin_domain = ClientUtils.extract_domain_from_referer_or_origin(origin) or \
                        ClientUtils.extract_domain_from_referer_or_origin(referer)

        if origin:
            if origin not in access_rules.allowed_origins:
                logger.warning(f"Access denied - Origin {origin} not allowed for client_id={client_id}")
                raise ForbiddenException(message=f"Origin {origin} not allowed")
        elif referer:
            if origin_domain not in access_rules.allowed_domains:
                logger.warning(f"Access denied - Domain {origin_domain} not allowed for client_id={client_id}")
                raise ForbiddenException(message=f"Domain {origin_domain} not allowed")

        # --- Signature Verification ---
        try:
            client_secret = await client_service.get_client_secret(client_id)
            await ClientUtils.verify_signature(request, client_secret)
        except Exception as e:
            logger.error(f"Access denied - Signature verification failed for client_id={client_id}: {str(e)}")
            raise ForbiddenException(message="Invalid request signature")

        logger.info(f"Client {client_id} passed authentication - IP: {client_ip}, Origin: {origin}")

        # --- Proceed with request ---
        response: Response = await call_next(request)

        # --- CORS Headers ---
        if origin and origin in access_rules.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type,x-client-id"
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response
