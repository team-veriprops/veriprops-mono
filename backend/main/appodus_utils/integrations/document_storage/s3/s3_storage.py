from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger
import asyncio
import os
from typing import Union, BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from kink import inject, di

from main.app.config.settings import settings
from main.appodus_utils.integrations.document_storage.interface import IDocumentStorageProvider

logger: Logger = di["logger"]


@inject
class S3DocumentStorageProvider(IDocumentStorageProvider):

    def __init__(self):
        if not settings.AWS_ACCESS_KEY or not settings.AWS_SECRET_ACCESS_KEY:
            raise ValueError("AWS credentials are missing in settings")

        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(region_name=settings.AWS_REGION_NAME, signature_version="s3v4")
        )

    @property
    def platform(self) -> str:
        return settings.AWS_S3_PLATFORM_NAME

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
    ) -> str:
        try:
            if hasattr(file_bytes, "read"):
                file_data = file_bytes.read()
            else:
                file_data = file_bytes

            logger.info(f"Uploading object to S3 bucket={bucket}, key={key}")
            cleaned_metadata = {k: str(v) for k, v in metadata.items()}
            extra_args: dict = {
                "ContentType": "application/pdf",
                "ACL": "private",
                "Metadata": cleaned_metadata,
            }
            if encrypted:
                extra_args["ServerSideEncryption"] = "AES256"
            await asyncio.to_thread(
                self.client.put_object,
                Bucket=bucket,
                Key=key,
                Body=file_data,
                ExtraArgs=extra_args,
            )
            return await self.get_presigned_url(key, bucket, expires_in_sec=settings.AWS_S3_PRESIGNED_URL_EXPIRES)
        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

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
                    "ACL": "private",  # Change if public access is required
                    "Metadata": cleaned_metadata
                }
            )

            os.remove(local_path)
            logger.info(f"Local PDF removed after upload: {local_path}")

            return await self.get_presigned_url(key, bucket, expires_in_sec=settings.AWS_S3_PRESIGNED_URL_EXPIRES)
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error while uploading PDF")
            raise HTTPException(status_code=500, detail=f"PDF processing error: {str(e)}")

    async def get_presigned_url(self, key: str, bucket: str, expires_in_sec: int = 3600) -> str:
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
            logger.error(f"Presigned URL generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Could not generate presigned URL: {e}")

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
            logger.error(f"Object deletion failed: {e}")
            raise HTTPException(status_code=500, detail=f"Could not delete document: {e}")
