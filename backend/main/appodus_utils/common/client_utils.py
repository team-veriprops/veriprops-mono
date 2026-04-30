import base64
import hashlib
import hmac
import ipaddress
import json
from typing import List, Optional, Union
from urllib.parse import urlparse, urlunparse

from cryptography.fernet import Fernet
from starlette.requests import Request

from main.appodus_utils.common.commons import Utils
from main.appodus_utils.common.utils_settings import utils_settings
from main.appodus_utils.exception.exceptions import ForbiddenException, UnauthorizedException

client_secret_encryption_key = utils_settings.APPODUS_CLIENT_SECRET_ENCRYPTION_KEY or ""
client_request_expires_seconds = utils_settings.APPODUS_CLIENT_REQUEST_EXPIRES_SECONDS or 300
fernet = Fernet(client_secret_encryption_key)

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
    def is_ip_allowed(ip: str, allowed_ips: List[str]) -> bool:
        try:
            client_ip = ipaddress.ip_address(ip)
            return any(client_ip == ipaddress.ip_address(allowed) for allowed in allowed_ips)
        except ValueError:
            return False

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

    @staticmethod
    def extract_domain_from_referer_or_origin(origin: Optional[str]) -> Optional[str]:
        try:
            from urllib.parse import urlparse
            if origin:
                parsed = urlparse(origin)
                return parsed.hostname
        except Exception:
            pass
        return None

    @staticmethod
    def encrypt_api_secret(secret: bytes) -> str:
        return fernet.encrypt(secret).decode()

    @staticmethod
    def decrypt_api_secret(encrypted_secret: str) -> str:
        return fernet.decrypt(encrypted_secret.encode()).decode()

    @staticmethod
    def compute_signature(client_secret: str, method: str, path: str, timestamp: str, body: bytes) -> str:
        """
        Used by the server

        :param client_secret:
        :param method:
        :param path:
        :param timestamp:
        :param body:
        :return:
        """
        body_hash = hashlib.sha256(body).hexdigest()

        canonical_msg = f"{method}\n{path}\n{str(timestamp)}\n{body_hash}"

        expected_signature = hmac.new(
            key=client_secret.encode(),
            msg=canonical_msg.encode(),
            digestmod=hashlib.sha256
        ).digest()

        expected_signature_b64 = base64.b64encode(expected_signature).decode()

        return expected_signature_b64

    @staticmethod
    def create_auth_headers(client_id: str, client_secret: str, method: str, path: str, body: Union[dict, list] = None) -> dict:
        """
        Used by the client

        :param client_id:
        :param client_secret:
        :param method:
        :param path:
        :param body:
        :return:
        """
        timestamp = str(Utils.datetime_now().timestamp())
        signature = ClientUtils.generate_signature(
            method=method,
            path=path,
            body=body or {},
            client_secret=client_secret,
            timestamp=timestamp,
        )
        return {
            "X-Client-ID": client_id,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        }

    @staticmethod
    def generate_signature(client_secret: str, method: str, path: str, body: Union[dict, list], timestamp: str) -> str:
        """
        Used by the client

        :param client_secret:
        :param method:
        :param path:
        :param body:
        :param timestamp:
        :return:
        """
        body_str = json.dumps(body)
        body_hash = hashlib.sha256(body_str.encode()).hexdigest()

        canonical_string = f"{method.upper()}\n{path}\n{timestamp}\n{body_hash}"

        signature = hmac.new(
            key=client_secret.encode(),
            msg=canonical_string.encode(),
            digestmod=hashlib.sha256
        ).digest()

        return base64.b64encode(signature).decode()

    @staticmethod
    async def verify_signature(request: Request, client_secret: str):
        client_id = request.headers.get("x-client-id")
        signature = request.headers.get("x-signature")
        timestamp = request.headers.get("x-timestamp")

        if not client_secret:
            raise ForbiddenException(message="Invalid Client ID")

        if not all([client_id, signature, timestamp]):
            raise UnauthorizedException(message="Missing headers")

        if not Utils.timestamp_now_minus_less_than(client_request_expires_seconds, timestamp):
            raise UnauthorizedException(message="Request expired")

        body = await request.body()
        path = str(request.url.path)
        method = request.method.upper()
        client_secret_decrypted = ClientUtils.decrypt_api_secret(client_secret)

        expected_signature = ClientUtils.compute_signature(client_secret_decrypted, method, path, timestamp, body)

        if not hmac.compare_digest(expected_signature, signature):
            raise ForbiddenException(message="Invalid signature")
