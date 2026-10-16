from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import asyncio
import os
from typing import BinaryIO, Optional, Union

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from kink import inject, di

from main.app.config.settings import settings
from main.appodus_utils.config.settings import FileStorage
from main.appodus_utils.integrations.document_storage.interface import IDocumentStorageProvider
from main.appodus_utils.integrations.exception.exceptions import IntegrationException

# Stored when the uploader did not say what the bytes are; S3 then serves them as a download.
_DEFAULT_CONTENT_TYPE = "application/octet-stream"

logger: Logger = di["logger"]


@inject
class S3DocumentStorageProvider(IDocumentStorageProvider):
    """Any S3-compatible store: AWS S3 when `STORAGE_ENDPOINT_URL` is blank, Cloudflare R2 (or
    another compatible store) at that endpoint otherwise."""

    # Only AWS S3 takes `ServerSideEncryption` on a put. R2 encrypts every object at rest and
    # does not implement the header, so it is sent only when no custom endpoint is configured.
    _request_sse: bool = True

    def __init__(self):
        if not settings.STORAGE_ACCESS_KEY_ID or not settings.STORAGE_SECRET_ACCESS_KEY:
            raise ValueError("Storage credentials are missing in settings")

        endpoint_url = settings.STORAGE_ENDPOINT_URL or None
        self._request_sse = endpoint_url is None
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY_ID,
            aws_secret_access_key=settings.STORAGE_SECRET_ACCESS_KEY,
            config=Config(region_name=settings.STORAGE_REGION, signature_version="s3v4")
        )

    @property
    def platform(self) -> str:
        # Serves both S3-compatible slots; never claims the stub's.
        if settings.STORAGE_PROVIDER in (FileStorage.S3, FileStorage.R2):
            return settings.STORAGE_PROVIDER
        return FileStorage.S3

    #
    # @staticmethod
    # def _get_s3_url(bucket: str, key: str) -> str:
    #     return f"https://{bucket}.s3.amazonaws.com/{key}"

    async def upload(
        self,
        key: str,
        bucket: str,
        file_bytes: Union[bytes, BinaryIO],
        metadata: dict,
        encrypted: bool = False,
        content_type: Optional[str] = None,
    ) -> str:
        """Store the bytes privately and return a short-lived read URL.

        Objects are private by default, so no ACL is sent: buckets with ACLs disabled (the AWS
        default since 2023) reject any ACL parameter outright.
        """
        if hasattr(file_bytes, "read"):
            file_data = file_bytes.read()
        else:
            file_data = file_bytes

        params: dict = {
            "Bucket": bucket,
            "Key": key,
            "Body": file_data,
            "ContentType": content_type or _DEFAULT_CONTENT_TYPE,
            "Metadata": {k: str(v) for k, v in metadata.items()},
        }
        if encrypted and self._request_sse:
            params["ServerSideEncryption"] = "AES256"

        try:
            logger.info(f"Uploading object to S3 bucket={bucket}, key={key}")
            await asyncio.to_thread(self.client.put_object, **params)
        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 upload failed for bucket={bucket}, key={key}: {e}")
            raise IntegrationException("Could not store the document.") from e
        return await self.get_presigned_url(key, bucket, expires_in_sec=settings.STORAGE_PRESIGNED_URL_EXPIRES)

    async def upload_local_doc(self, key: str, bucket: str, local_path: str, metadata: dict) -> str:
        if not os.path.exists(local_path):
            logger.warning(f"Local file not found at {local_path}")
            raise HTTPException(status_code=404, detail="Local PDF file not found")

        try:
            logger.info(f"Uploading contract PDF to S3: {bucket}/{key}")
            cleaned_metadata = {k: str(v) for k, v in metadata.items()}
            await asyncio.to_thread(
                self.client.upload_file,
                Filename=local_path,
                Bucket=bucket,
                Key=key,
                ExtraArgs={
                    "ContentType": "application/pdf",
                    "Metadata": cleaned_metadata
                }
            )

            os.remove(local_path)
            logger.info(f"Local PDF removed after upload: {local_path}")

            return await self.get_presigned_url(key, bucket, expires_in_sec=settings.STORAGE_PRESIGNED_URL_EXPIRES)
        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 upload failed for bucket={bucket}, key={key}: {e}")
            raise IntegrationException("Could not store the document.") from e

    async def get_presigned_url(
        self, key: str, bucket: str, expires_in_sec: int = settings.STORAGE_PRESIGNED_URL_EXPIRES
    ) -> str:
        try:
            logger.info(f"Generating presigned URL for {bucket}/{key}")
            url = await asyncio.to_thread(
                self.client.generate_presigned_url,
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in_sec
            )
            return url
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Presigned URL generation failed for bucket={bucket}, key={key}: {e}")
            raise IntegrationException("Could not open the document.") from e

    async def delete(self, key: str, bucket: str) -> None:
        """Delete an object from S3."""
        try:
            logger.info(f"Deleting object from S3 bucket={bucket}, key={key}")
            await asyncio.to_thread(
                self.client.delete_object,
                Bucket=bucket,
                Key=key,
            )
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Object deletion failed for bucket={bucket}, key={key}: {e}")
            raise IntegrationException("Could not delete the document.") from e

    async def delete_prefix(self, prefix: str, bucket: str) -> int:
        """List every object under ``prefix`` (1,000 per page) and delete each page in one call."""
        if not prefix:
            raise ValueError("Refusing to delete a whole bucket: the prefix is empty.")
        deleted = 0
        token = None
        try:
            while True:
                page_args = {"Bucket": bucket, "Prefix": prefix, **({"ContinuationToken": token} if token else {})}
                page = await asyncio.to_thread(self.client.list_objects_v2, **page_args)
                keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
                if keys:
                    await asyncio.to_thread(
                        self.client.delete_objects, Bucket=bucket, Delete={"Objects": keys, "Quiet": True},
                    )
                    deleted += len(keys)
                if not page.get("IsTruncated"):
                    return deleted
                token = page.get("NextContinuationToken")
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Prefix deletion failed for bucket={bucket}, prefix={prefix}: {e}")
            raise IntegrationException("Could not delete the documents.") from e
