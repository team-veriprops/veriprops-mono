from typing import Optional
from urllib.parse import urlparse, urlunparse

from starlette.requests import Request


class ClientUtils:

    @staticmethod
    def get_client_ip(request: Request) -> str:
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            # X-Forwarded-For may contain a list of IPs
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host
        return ip

    @staticmethod
    def get_user_agent(request: Request) -> Optional[str]:
        return request.headers.get("user-agent")

    @staticmethod
    def get_referer_domain(request: Request) -> str:
        referer_url = request.headers.get("referer")
        parsed_referer_url = urlparse(referer_url)

        return urlunparse((
            parsed_referer_url.scheme,
            parsed_referer_url.netloc,
            "",
            "",
            "",
            ""
        ))
