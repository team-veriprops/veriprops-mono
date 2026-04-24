import base64
import hashlib
import hmac
import json
import tempfile
from io import BytesIO
from typing import Type, List

from fastapi import UploadFile, FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete
from starlette.datastructures import UploadFile as StarletteUploadFile, Headers

from main.appodus_utils import BaseEntity
from main.appodus_utils.db.session import create_new_db_session

class TestUtils:
    @staticmethod
    def create_mock_upload_file(filename: str = "test-file.pdf", content: bytes = b"test content",
                                content_type: str = "application/pdf") -> UploadFile:
        file = BytesIO(content)
        headers = Headers({
            "content-type": content_type
        })
        upload_file = StarletteUploadFile(filename=filename, file=file, headers=headers)
        return upload_file


    @staticmethod
    def get_real_temp_file_path():
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            return tmp.name  # The file exists on disk until you manually delete it


    @staticmethod
    async def truncate_entities(entities: List[Type[BaseEntity]]):
        async with create_new_db_session() as db_session:
            async with db_session.begin():
                for entity in entities:
                    stmt = delete(entity)
                    await db_session.execute(stmt)

    @staticmethod
    def get_app_test_client(app: FastAPI):
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        return client

    @staticmethod
    def generate_signature(method: str, path: str, body: dict, client_secret: str, timestamp: str) -> str:
        body_json = json.dumps(body)
        body_hash = hashlib.sha256(body_json.encode()).hexdigest()

        canonical_string = f"{method.upper()}\n{path}\n{timestamp}\n{body_hash}"

        signature = hmac.new(
            key=client_secret.encode(),
            msg=canonical_string.encode(),
            digestmod=hashlib.sha256
        ).digest()

        return base64.b64encode(signature).decode()
