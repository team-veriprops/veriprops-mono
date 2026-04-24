import os
import unittest
from unittest.mock import AsyncMock, MagicMock


from main.app.config.bootstrap import bootstrap_di
from main.app.utils.decorators.decorate_all_methods import decorate_all_methods
from main.app.utils.decorators.transactional import transactional, TransactionSessionPolicy

bootstrap_di()
from main.appodus_utils import Page
from parameterized import parameterized
from main.app.config.settings import FileStorage
from main.app.domain.file.models import (UpdateStoredFileDto, SearchStoredFileDto, QueryStoredFileDto, FileOwner,
                                         FileType)
from main.app.domain.file.service import StoredFileService
from test.e2e.app.domain.file.file_utils import get_create_file_dto
from test.utils.test_utils import get_real_temp_file_path, create_mock_upload_file

@decorate_all_methods(transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW),
                      exclude=['__init__', 'asyncSetUp', 'asyncTearDown'], exclude_startswith='_')
class TestStoredFileService(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.local_path = get_real_temp_file_path()
        self.upload_file = create_mock_upload_file()

        self.upload_response = "https://s3.url/file.png"
        self.upload_contract_pdf_response = "https://s3.url/sample.pdf"

        self.file_repo = AsyncMock()
        self.file_validator = AsyncMock()

        self.document_storage_provider = AsyncMock()
        self.document_storage_provider.upload.return_value = self.upload_response
        self.document_storage_provider.upload_contract_pdf.return_value = self.upload_contract_pdf_response
        self.document_storage_provider.get_presigned_url.return_value = self.upload_response

        self.document_storage_provider_factory = MagicMock()
        self.document_storage_provider_factory.get_active_provider.return_value = self.document_storage_provider

        self.service = StoredFileService(file_repo=self.file_repo, file_validator=self.file_validator,
            document_storage_provider_factory=self.document_storage_provider_factory, )

        self.query_stored_file = QueryStoredFileDto(owner=FileOwner.PROPERTY, type=FileType.PROPERTY_CONTRACT,
            store_bucket='bucket-name', storage=FileStorage.S3, store_key="store-key", filename="old.png",
            url="old-url")

    async def asyncTearDown(self):
        os.unlink(self.local_path)

    @parameterized.expand([("with_upload_file", True), ("with_file_path", False), ])
    async def test_create_file(self, _, use_file):
        # Arrange
        file_path = self.local_path if not use_file else None
        file = self.upload_file if use_file else None
        create_file_dto = get_create_file_dto(file=file, file_path=file_path)
        file_url = self.upload_response if use_file else self.upload_contract_pdf_response

        self.query_stored_file.url = file_url
        self.file_repo.create.return_value = self.query_stored_file

        # Act
        result = await self.service.create_file(create_file_dto)

        # Assert
        self.assertIsInstance(result, QueryStoredFileDto)
        self.assertEqual(result.url, file_url)
        self.file_repo.create.assert_awaited_once()

    async def test_update_file_with_upload(self):
        file_id = "123"
        update_dto = UpdateStoredFileDto(file=self.upload_file, metadata={"updated": True})

        self.file_repo.get.return_value = self.query_stored_file

        result = await self.service.update_file(file_id, update_dto)

        self.assertTrue(result)
        self.file_validator.should_exist_by_id.assert_awaited_once_with(file_id)
        self.file_repo.update.assert_awaited_once()

    async def test_get_file_page(self):
        search_dto = SearchStoredFileDto(owner=FileOwner.USER, type=FileType.PROFILE, )
        page = Page(items=[], total=0, count=0, next_page=0, prev_page=0, page=1, page_size=10)
        self.file_repo.get_page.return_value = page

        result = await self.service.get_file_page(search_dto)

        self.assertEqual(result, page)
        self.file_repo.get_page.assert_awaited_once_with(search_dto=search_dto)

    async def test_get_file(self):
        file_id = "abc123"
        self.file_validator.should_exist_by_id.return_value = None
        self.file_repo.get.return_value = self.query_stored_file

        result = await self.service.get_file(file_id)

        self.assertEqual(result, self.query_stored_file)
        self.file_validator.should_exist_by_id.assert_awaited_once_with(file_id)
        self.file_repo.get.assert_awaited_once_with(file_id)

    async def test_get_presigned_url(self):
        file_id = "abc"
        self.file_repo.get.return_value = self.query_stored_file

        result = await self.service.get_presigned_url(file_id)

        self.assertEqual(result, self.upload_response)
        self.document_storage_provider.get_presigned_url.assert_awaited_once_with(self.query_stored_file.store_key,
            self.query_stored_file.store_bucket, 3600)

    async def test_soft_delete_files(self):
        file_id = "file-123"
        self.file_repo.soft_delete.return_value = True

        result = await self.service.soft_delete_files(file_id)

        self.assertTrue(result)
        self.file_repo.soft_delete.assert_awaited_once_with(file_id)
