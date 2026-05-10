from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import json
import urllib.parse
from datetime import timedelta
from typing import Optional, Tuple
from urllib.parse import urlparse

from kink import di
from starlette.requests import Request
from starlette.responses import HTMLResponse

from main.app.config.settings import settings
from main.app.domain.user.auth.oauth.providers.models import (
    OAuthFlowMode,
    OAuthRequestStoredState,
    SocialAuthProvider,
)
from main.app.domain.user.auth.utils.jwt_auth_utils import JwtAuthUtils
from main.appodus_utils.db.redis_utils import RedisUtils
from main.appodus_utils.decorators.decorate_all_methods import decorate_all_methods
from main.appodus_utils.decorators.method_trace_logger import method_trace_logger
from main.appodus_utils.exception.exceptions import ForbiddenException

logger: Logger = di["logger"]


def _allowed_frontend_origins() -> list[str]:
    raw = settings.OAUTH_FRONTEND_ORIGINS or ""
    return [o.strip() for o in raw.split(",") if o.strip()]


@decorate_all_methods(method_trace_logger)
class OauthUtils:

    @staticmethod
    async def init_0auth(
        platform: SocialAuthProvider,
        request: Request,
        base_url: str,
        client_id: str,
        scope: str,
        intent: Optional[str] = None,
        mode: OAuthFlowMode = OAuthFlowMode.AUTH,
        link_user_id: Optional[str] = None,
    ) -> str:
        """Build the provider authorization URL, persist signed state + PKCE
        verifier in Redis, and return the URL for the popup to navigate to."""
        code_challenge, code_verifier, state = JwtAuthUtils.generate_pkce()
        redirect_uri = await OauthUtils.callback_redirect_uri(platform)
        frontend_origin = await OauthUtils.resolve_frontend_origin(request)

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if platform == SocialAuthProvider.APPLE:
            # Apple delivers the callback as form_post (POST). Required when
            # `name email` scopes are requested.
            params["response_mode"] = "form_post"

        oauth_request_payload = OAuthRequestStoredState(
            code_verifier=code_verifier,
            intent=intent or "default",
            frontend_origin=frontend_origin,
            mode=mode,
            link_user_id=link_user_id,
        )

        await RedisUtils.set_redis(f"oauth:state:{state}", oauth_request_payload, time_to_live=timedelta(minutes=10))

        query_string = urllib.parse.urlencode(params)
        return f"{base_url}?{query_string}"

    @staticmethod
    async def callback_redirect_uri(platform: SocialAuthProvider) -> str:
        """The OAuth redirect_uri registered with each provider. Must point at
        this backend (not the frontend) — the popup loads the backend HTML
        callback page, which then postMessages the parent frame and closes."""
        return f"{settings.BACKEND_PUBLIC_ORIGIN.rstrip('/')}/api/users/auth/oauth/{platform.value}/callback"

    @staticmethod
    async def resolve_frontend_origin(request: Request) -> str:
        """Pick the frontend origin that opened the popup. Validated against
        the allowlist so we can later use it as a `postMessage` targetOrigin
        without spoofing risk. Falls back to the first allowlisted origin if
        no Referer/Origin is present (e.g. unit tests)."""
        candidates = []
        origin_hdr = request.headers.get("origin")
        referer_hdr = request.headers.get("referer")
        if origin_hdr:
            candidates.append(origin_hdr)
        if referer_hdr:
            parsed = urlparse(referer_hdr)
            if parsed.scheme and parsed.netloc:
                candidates.append(f"{parsed.scheme}://{parsed.netloc}")

        allowed = _allowed_frontend_origins()
        if not allowed:
            raise ForbiddenException(message="No OAuth frontend origin allowlist configured.")

        for c in candidates:
            normalised = c.rstrip("/")
            if normalised in allowed:
                return normalised

        # Request supplied an explicit origin/referer that is not on the allowlist — reject.
        if candidates:
            raise ForbiddenException(message="OAuth origin not permitted.")

        # No origin/referer header (server-to-server or unit test). Default to first allowlisted.
        return allowed[0]

    @staticmethod
    async def consume_state(state: Optional[str]) -> Optional[OAuthRequestStoredState]:
        """Atomically pop a stored OAuth state. Single-use: if we successfully
        delete the key, we own the value; concurrent callers see None."""
        if not state:
            return None
        key = f"oauth:state:{state}"
        stored: Optional[OAuthRequestStoredState] = await RedisUtils.get_redis(key)
        await RedisUtils.delete(key)
        return stored

    @staticmethod
    async def popup_response(
        *,
        success: bool,
        target_origin: str,
        state: Optional[str] = None,
        message: Optional[str] = None,
        extra_headers: Optional[dict] = None,
    ) -> HTMLResponse:
        """Minimal HTML returned by the OAuth callback. It posts a single
        `oauth_result` message to the popup opener and self-closes. The parent
        validates `event.origin` and `event.data.type` before acting."""
        payload = {"type": "oauth_result", "success": bool(success), "state": state}
        if message:
            payload["message"] = message
        payload_json = json.dumps(payload)
        target_js = json.dumps(target_origin)
        body_text = "Sign-in complete. You can close this window." if success else (
            message or "Sign-in failed. You can close this window."
        )
        html = f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<title>Veriprops — Sign in</title>
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<style>
  body {{ font-family: -apple-system, system-ui, Segoe UI, Roboto, sans-serif;
          background: #0b0d10; color: #e6e8eb; display: flex;
          align-items: center; justify-content: center; height: 100vh; margin: 0; }}
  .card {{ max-width: 320px; padding: 24px; text-align: center; }}
  .muted {{ color: #9aa3ad; font-size: 14px; margin-top: 8px; }}
</style>
</head>
<body>
<div class=\"card\">
  <p>{body_text}</p>
  <p class=\"muted\">If this window did not close automatically, you can close it now.</p>
</div>
<script>
(function () {{
  try {{
    if (window.opener && !window.opener.closed) {{
      window.opener.postMessage({payload_json}, {target_js});
    }}
  }} catch (_) {{}}
  setTimeout(function () {{ try {{ window.close(); }} catch (_) {{}} }}, 200);
}})();
</script>
</body>
</html>"""
        response = HTMLResponse(content=html, status_code=200)
        if extra_headers:
            for k, v in extra_headers.items():
                response.headers[k] = v
        return response
