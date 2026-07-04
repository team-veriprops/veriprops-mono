"""Deterministic document-storage provider for tests/local dev.

Mirrors the OTP / payment / KYC stub philosophy: no external calls, no AWS
credentials required, fully deterministic. Selected when
``AWS_S3_PLATFORM_NAME == FileStorage.STUB`` (or by the evidence service under
``DOCUMENT_STORAGE_STUB_MODE``). Returns a synthetic, stable URL derived from the
object key so the rest of the pipeline (content-hash, GPS/timestamp stamping,
evidence rows) is exercised end-to-end without a real bucket.
"""
from __future__ import annotations

from typing import BinaryIO, Union

from kink import inject

from main.appodus_utils.config.settings import FileStorage
from main.appodus_utils.integrations.document_storage.interface import IDocumentStorageProvider


@inject
class StubDocumentStorageProvider(IDocumentStorageProvider):
    @property
    def platform(self) -> str:
        return FileStorage.STUB

    async def upload(
        self,
        key: str,
        bucket: str,
        file_bytes: Union[bytes, BinaryIO],
        metadata: dict,
        encrypted: bool = False,
    ) -> str:
        # Drain a file-like body so callers behave identically to the real provider.
        if hasattr(file_bytes, "read"):
            file_bytes.read()
        return await self.get_presigned_url(key, bucket)

    async def upload_local_doc(self, key: str, bucket: str, local_path: str, metadata: dict) -> str:
        return await self.get_presigned_url(key, bucket)

    async def get_presigned_url(self, key: str, bucket: str, expires_in_sec: int = 3600) -> str:
        return f"stub-storage://{bucket}/{key}"

    async def delete(self, key: str, bucket: str) -> None:
        return None
