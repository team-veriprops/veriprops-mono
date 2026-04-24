from typing import Union, BinaryIO, Optional

from _pytest.monkeypatch import MonkeyPatch
from fastapi import UploadFile
from kink import di

from main.app.domain.file.models import CreateStoredFileDto, FileOwner, FileType
from main.appodus_utils.integrations.document_storage import IDocumentStorageProvider
from main.appodus_utils.integrations.document_storage.factory import DocumentStorageProviderFactory

def get_create_file_dto(file: UploadFile = None, file_path: str = None):
    return CreateStoredFileDto(
        owner=FileOwner.PROPERTY,
        type=FileType.PROPERTY_CONTRACT,
        store_bucket='bucket-name',
        store_key="contracts/contract_uihef/user_jhdhw.pdf",
        file_path=file_path,
        file=file,
        metadata={"doc_type": "contract"},
    )

def mock_document_storage_provider(
        monkeypatch: MonkeyPatch,
        _s3_key: str,
        _bucket: str,
        _local_path: Optional[str],
        _file_bytes: Optional[Union[bytes, BinaryIO]],
        _metadata: dict,
        called_methods: dict,
        response: str,
        validate:bool=True):
    document_storage_provider_factory: DocumentStorageProviderFactory = di[DocumentStorageProviderFactory]
    document_storage_provider: IDocumentStorageProvider = document_storage_provider_factory.get_active_provider()

    # upload_contract_pdf
    async def mock_upload_contract_pdf(s3_key: str, bucket: str, local_path: str, metadata: dict):
        if validate:
            assert s3_key == _s3_key
            assert bucket == _bucket
            assert local_path == _local_path
            assert metadata == _metadata

            called_methods["upload_contract_pdf_called"] = True

        return response

    monkeypatch.setattr(document_storage_provider, "upload_contract_pdf", mock_upload_contract_pdf)

    # upload
    async def mock_upload(s3_key: str, bucket: str, file_bytes: Union[bytes, BinaryIO]) -> str:
        if validate:
            assert s3_key == _s3_key
            assert bucket == _bucket
            assert file_bytes == _file_bytes

            called_methods["upload_called"] = True

        return response

    monkeypatch.setattr(document_storage_provider, "upload", mock_upload)