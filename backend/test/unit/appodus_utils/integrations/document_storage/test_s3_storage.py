"""S3DocumentStorageProvider contract against botocore's Stubber — no network, no bucket.

Staging and production store every agent's evidence through this adapter, and the
drive-through runs on the stub, so these tests are what pins the real call shapes:
the exact `put_object` parameters S3 accepts, a presigned GET for reads, delete, and
a failure that answers with a safe sentence rather than boto's own text.
"""
import boto3
import pytest
from botocore.config import Config
from botocore.stub import ANY, Stubber

from main.appodus_utils.integrations.document_storage.s3.s3_storage import S3DocumentStorageProvider
from main.appodus_utils.integrations.exception.exceptions import IntegrationException

BUCKET = "veriprops-documents-test"
KEY = "evidence/v-1/t-1/abc123"


@pytest.fixture
def provider():
    """The provider with a real boto3 client that only ever talks to the Stubber."""
    s3 = object.__new__(S3DocumentStorageProvider)
    s3.client = boto3.client(
        "s3",
        aws_access_key_id="test-access-key",
        aws_secret_access_key="test-secret-key",
        config=Config(region_name="us-east-1", signature_version="s3v4"),
    )
    return s3


@pytest.fixture
def stubber(provider):
    with Stubber(provider.client) as stub:
        yield stub
        stub.assert_no_pending_responses()


async def test_upload_sends_a_put_object_s3_accepts(provider, stubber):
    stubber.add_response(
        "put_object",
        {"ETag": '"etag"'},
        {
            "Bucket": BUCKET,
            "Key": KEY,
            "Body": b"jpeg-bytes",
            "ContentType": "image/jpeg",
            "Metadata": {"task_id": "t-1", "size": "10"},
            "ServerSideEncryption": "AES256",
        },
    )

    url = await provider.upload(
        key=KEY, bucket=BUCKET, file_bytes=b"jpeg-bytes",
        metadata={"task_id": "t-1", "size": 10}, encrypted=True, content_type="image/jpeg",
    )

    assert url.startswith(f"https://{BUCKET}.s3.amazonaws.com/{KEY}")
    assert "X-Amz-Signature=" in url


async def test_an_unencrypted_upload_of_unknown_type_is_stored_as_octet_stream(provider, stubber):
    stubber.add_response(
        "put_object",
        {"ETag": '"etag"'},
        {"Bucket": BUCKET, "Key": KEY, "Body": ANY, "ContentType": "application/octet-stream", "Metadata": {}},
    )

    await provider.upload(key=KEY, bucket=BUCKET, file_bytes=b"bytes", metadata={})


async def test_presigned_url_is_a_signed_get_that_expires(provider):
    url = await provider.get_presigned_url(KEY, BUCKET, expires_in_sec=900)

    assert f"{BUCKET}.s3.amazonaws.com/{KEY}" in url
    assert "X-Amz-Expires=900" in url


async def test_delete_removes_the_object(provider, stubber):
    stubber.add_response("delete_object", {}, {"Bucket": BUCKET, "Key": KEY})

    await provider.delete(KEY, BUCKET)


async def test_a_failed_upload_answers_with_a_safe_sentence(provider, stubber):
    stubber.add_client_error(
        "put_object", service_error_code="AccessDenied",
        service_message="User arn:aws:iam::123456789012:user/secret-name is not authorized",
        http_status_code=403,
    )

    with pytest.raises(IntegrationException) as caught:
        await provider.upload(key=KEY, bucket=BUCKET, file_bytes=b"x", metadata={})

    assert caught.value.status_code == 502
    assert "arn:aws" not in str(caught.value)
    assert "AccessDenied" not in str(caught.value)
