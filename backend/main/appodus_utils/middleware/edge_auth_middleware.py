import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from main.appodus_utils.config.settings import SECRET_PLACEHOLDER


class EdgeAuthMiddleware(BaseHTTPMiddleware):
    """Rejects requests that did not traverse the trusted edge proxy (Cloudflare).

    The proxy injects `header_name: secret` on every request via a Transform Rule,
    so traffic that reaches the origin directly — e.g. a *.vercel.app deployment
    URL, or the raw origin address on self-hosted — lacks the header and is
    refused. This is what makes the WAF/proxy an enforced boundary instead of an
    optional route.

    Disabled when the secret is blank or the shared placeholder, so local, test,
    and e2e environments run open without extra configuration. No path exemptions:
    webhooks, SSE, and OAuth all arrive via the public (proxied) hostnames and
    carry the header; ACME/`.well-known` traffic is handled at the platform edge
    before the app.
    """

    def __init__(self, app, secret: str = "", header_name: str = "x-edge-auth"):
        super().__init__(app)
        cleaned = (secret or "").strip()
        self._secret = "" if cleaned == SECRET_PLACEHOLDER else cleaned
        self._header_name = header_name

    async def dispatch(self, request: Request, call_next):
        if not self._secret:
            return await call_next(request)

        supplied = request.headers.get(self._header_name, "")
        if not hmac.compare_digest(supplied.encode(), self._secret.encode()):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "EDGE_AUTH_REQUIRED",
                        "message": "Requests must come through the trusted edge.",
                    }
                },
            )
        return await call_next(request)
