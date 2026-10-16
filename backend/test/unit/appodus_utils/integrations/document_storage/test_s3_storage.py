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

from main.app.config.settings import settings
from main.appodus_utils.config.settings import FileStorage
from main.appodus_utils.integrations.document_storage.s3 import s3_storage
from main.appodus_utils.integrations.document_storage.s3.s3_storage import S3DocumentStorageProvider
from main.appodus_utils.integrations.exception.exceptions import IntegrationException

R2_ENDPOINT = "https://account-id.r2.cloudflarestorage.com"

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


async def test_an_encrypted_upload_to_r2_sends_no_sse_header(provider, stubber):
    # R2 encrypts every object at rest and does not implement `x-amz-server-side-encryption`.
    provider._request_sse = False
    stubber.add_response(
        "put_object",
        {"ETag": '"etag"'},
        {"Bucket": BUCKET, "Key": KEY, "Body": ANY, "ContentType": "image/jpeg", "Metadata": {}},
    )

    await provider.upload(key=KEY, bucket=BUCKET, file_bytes=b"x", metadata={}, encrypted=True,
                          content_type="image/jpeg")


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


async def test_delete_prefix_deletes_every_page_under_the_prefix(provider, stubber):
    prefix = "kyc/u-1/"
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "kyc/u-1/a/selfie"}], "IsTruncated": True, "NextContinuationToken": "t-2"},
        {"Bucket": BUCKET, "Prefix": prefix},
    )
    stubber.add_response(
        "delete_objects", {}, {"Bucket": BUCKET, "Delete": {"Objects": [{"Key": "kyc/u-1/a/selfie"}], "Quiet": True}},
    )
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "kyc/u-1/b/selfie"}, {"Key": "kyc/u-1/b/document"}], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": prefix, "ContinuationToken": "t-2"},
    )
    stubber.add_response(
        "delete_objects", {},
        {"Bucket": BUCKET, "Delete": {"Objects": [{"Key": "kyc/u-1/b/selfie"}, {"Key": "kyc/u-1/b/document"}], "Quiet": True}},
    )

    assert await provider.delete_prefix(prefix, BUCKET) == 3
    stubber.assert_no_pending_responses()


async def test_delete_prefix_refuses_an_empty_prefix(provider):
    with pytest.raises(ValueError):
        await provider.delete_prefix("", BUCKET)


class TestClientConfiguration:
    """Which store the client talks to, with which keys, is decided by the STORAGE_* settings."""

    @staticmethod
    def _build(monkeypatch, **overrides):
        for name, value in overrides.items():
            monkeypatch.setattr(settings, name, value)
        captured: dict = {}

        def fake_client(service, **kwargs):
            captured.update(service=service, **kwargs)
            return object()

        monkeypatch.setattr(s3_storage.boto3, "client", fake_client)
        return S3DocumentStorageProvider(), captured

    def test_r2_is_reached_through_its_endpoint_with_the_storage_keys(self, monkeypatch):
        provider, client = self._build(
            monkeypatch, STORAGE_PROVIDER=FileStorage.R2, STORAGE_ENDPOINT_URL=R2_ENDPOINT,
            STORAGE_REGION="auto", STORAGE_ACCESS_KEY_ID="r2-key-id", STORAGE_SECRET_ACCESS_KEY="r2-secret",
        )

        assert client["service"] == "s3"
        assert client["endpoint_url"] == R2_ENDPOINT
        assert client["aws_access_key_id"] == "r2-key-id"
        assert client["aws_secret_access_key"] == "r2-secret"
        assert client["config"].region_name == "auto"
        assert provider.platform == FileStorage.R2
        assert provider._request_sse is False

    def test_a_blank_endpoint_means_aws_s3(self, monkeypatch):
        provider, client = self._build(
            monkeypatch, STORAGE_PROVIDER=FileStorage.S3, STORAGE_ENDPOINT_URL="",
            STORAGE_ACCESS_KEY_ID="aws-key-id", STORAGE_SECRET_ACCESS_KEY="aws-secret",
        )

        assert client["endpoint_url"] is None
        assert provider.platform == FileStorage.S3
        assert provider._request_sse is True

    def test_it_never_claims_the_stubs_slot(self, monkeypatch):
        provider, _ = self._build(monkeypatch, STORAGE_PROVIDER=FileStorage.STUB)

        assert provider.platform == FileStorage.S3
