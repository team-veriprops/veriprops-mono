import os
import unittest
from unittest.mock import AsyncMock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import UploadFile
from kink import di
from parameterized import parameterized

from main.app.domain.file.models import (UpdateStoredFileDto, SearchStoredFileDto, QueryStoredFileDto, FileOwner,
                                         FileType, StoredFile)
from main.app.domain.file.service import StoredFileService
from main.appodus_utils.integrations.document_storage.factory import DocumentStorageProviderFactory
from main.app.utils.decorators.decorate_all_methods import decorate_all_methods
from main.app.utils.decorators.transactional import transactional, TransactionSessionPolicy
from test.e2e.app.domain.file.file_utils import mock_document_storage_provider, get_create_file_dto
from test.utils.test_utils import truncate_entities, get_real_temp_file_path, create_mock_upload_file


@decorate_all_methods(transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW),
                      exclude=['__init__', 'asyncSetUp', 'asyncTearDown'], exclude_startswith='_')
class TestStoredFileService(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.stored_file_service: StoredFileService = di[StoredFileService]
        self.document_storage_provider_factory: DocumentStorageProviderFactory = di[DocumentStorageProviderFactory]

        self.document_storage_provider = self.document_storage_provider_factory.get_active_provider()
        self.local_path = get_real_temp_file_path()
        self.upload_file = create_mock_upload_file()

        self.upload_response = "https://s3.url/file.png"

        # Just to confirm mocked methods called
        self.called_methods = {"upload_contract_pdf_called": False, "upload_called": False}

        self.monkeypatch = MonkeyPatch()

    async def asyncTearDown(self):
        self._reset_called_methods()
        os.unlink(self.local_path)
        self.monkeypatch.undo()
        await self._truncate_tables()

    def _reset_called_methods(self):
        self.called_methods = {"upload_contract_pdf_called": False, "upload_called": False}

    @staticmethod
    async def _truncate_tables():
        await truncate_entities([StoredFile])

    async def _create_file(self, file: UploadFile = None, file_path: str = None):
        file_path = self.local_path
        file = self.upload_file
        create_file_dto = get_create_file_dto(file=file, file_path=file_path)

        mock_document_storage_provider(
            monkeypatch=self.monkeypatch,
            _s3_key=create_file_dto.store_key,
            _bucket=create_file_dto.store_bucket,
            _local_path=create_file_dto.file_path,
            _file_bytes=create_file_dto.file.file if create_file_dto.file else None,
            _metadata=create_file_dto.metadata,
            called_methods=self.called_methods,
            response=self.upload_response,
            validate=False)

        create_file_dto = get_create_file_dto(file=file, file_path=file_path)
        return await self.stored_file_service.create_file(create_file_dto)

    @parameterized.expand([("with_upload_file", True, True, False), ("with_file_path", False, False, True), ])
    async def test_create_file(self, _, use_file, upload_called, upload_contract_pdf_called):
        # Arrange
        file_path = self.local_path if not use_file else None
        file = self.upload_file if use_file else None
        create_file_dto = get_create_file_dto(file=file, file_path=file_path)

        mock_document_storage_provider(
            monkeypatch=self.monkeypatch,
            _s3_key=create_file_dto.store_key,
            _bucket=create_file_dto.store_bucket,
            _local_path=create_file_dto.file_path,
            _file_bytes=create_file_dto.file.file if create_file_dto.file else None,
            _metadata=create_file_dto.metadata,
            called_methods=self.called_methods,
            response=self.upload_response)

        # Act
        result = await self.stored_file_service.create_file(create_file_dto)

        # Assert
        self.assertIsInstance(result, QueryStoredFileDto)
        self.assertEqual(result.url, self.upload_response)

        assert self.called_methods["upload_contract_pdf_called"] is upload_contract_pdf_called
        assert self.called_methods["upload_called"] is upload_called

    async def test_update_file_with_upload(self):
        created_file = await self._create_file(file_path=self.local_path)
        update_dto = UpdateStoredFileDto(file=self.upload_file, metadata={"updated": True})

        mock_document_storage_provider(monkeypatch=self.monkeypatch, _s3_key=created_file.store_key,
            _bucket=created_file.store_bucket, _local_path=self.local_path, _file_bytes=update_dto.file.file,
            _metadata={}, called_methods=self.called_methods, response=self.upload_response)

        result = await self.stored_file_service.update_file(created_file.id, update_dto)

        self.assertTrue(result)
        self.assertTrue(self.called_methods["upload_called"])

    async def test_get_file_page(self):
        await self._create_file(file_path=self.local_path)
        await self._create_file(file=self.upload_file)

        search_dto = SearchStoredFileDto(page=0, page_size=10, owner=FileOwner.PROPERTY,
                                         type=FileType.PROPERTY_CONTRACT, )

        result = await self.stored_file_service.get_file_page(search_dto)

        self.assertEqual(len(result.data), 2)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.count, 2)

    async def test_get_file(self):
        created_file = await self._create_file(file_path=self.local_path)

        result = await self.stored_file_service.get_file(created_file.id)

        self.assertIsNotNone(result)
        self.assertEqual(created_file.id, result.id)

    async def test_get_presigned_url(self):
        created_file = await self._create_file(file_path=self.local_path)

        self.document_storage_provider.get_presigned_url = AsyncMock(return_value=self.upload_response)

        result = await self.stored_file_service.get_presigned_url(created_file.id)

        self.assertEqual(result, self.upload_response)
        self.document_storage_provider.get_presigned_url.assert_awaited_once_with(created_file.store_key,
                                                                                  created_file.store_bucket, 3600)

    async def test_soft_delete_files(self):
        created_file = await self._create_file(file_path=self.local_path)

        result = await self.stored_file_service.soft_delete_files(created_file.id)

        self.assertTrue(result)
