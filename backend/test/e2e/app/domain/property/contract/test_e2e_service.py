import unittest
from decimal import Decimal

from _pytest.monkeypatch import MonkeyPatch
from kink import di

from main.app.config.settings import settings
from main.appodus_utils import Utils
from main.app.db.types.money import Money, TransactionCurrency
from main.app.domain.file.models import StoredFile
from main.app.domain.property.contract.final.models import FinalContract
from main.app.domain.property.contract.models import UpdatePropertyContractDto, \
    ContractType, PropertyContract, SearchPropertyContractDto
from main.app.domain.property.contract.service import PropertyContractService
from main.app.domain.property.contract.template.models import ContractTemplate
from main.app.utils.decorators.decorate_all_methods import decorate_all_methods
from main.app.utils.decorators.transactional import transactional, TransactionSessionPolicy
from test.e2e.app.domain.file.file_utils import mock_document_storage_provider
from test.e2e.app.domain.property.contract.template.contract_utils import mock_google_drive_client, \
    create_contract_template_dto, create_property_contract_dto, create_property_contract, create_contract_template
from test.utils.test_utils import get_app_test_client, truncate_entities, get_real_temp_file_path, \
    create_mock_upload_file

property_contract_service: PropertyContractService = di[PropertyContractService]

@decorate_all_methods(transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW),
                      exclude=['__init__', 'asyncSetUp', 'asyncTearDown'], exclude_startswith='_')
class TestPropertyContractService(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.client = get_app_test_client()
        self.client_endpoint = "api/properties/contracts/"

        self.local_pdf_path = get_real_temp_file_path()

        self.monkeypatch = MonkeyPatch()
        new_doc_name = Utils.get_contract_title(
            create_contract_template_dto.title,
            create_property_contract_dto.property_id)
        mock_google_drive_client(
            monkeypatch=self.monkeypatch,
            _file_id=settings.GOOGLE_DOC_PARENT_CONTRACT_ID,
            _new_name=new_doc_name,
            _email=create_property_contract_dto.seller_google_email,
            _pdf_path=self.local_pdf_path
        )

    async def asyncTearDown(self):
        self.monkeypatch.undo()
        await self._truncate_tables()
        await self.client.aclose()

    @staticmethod
    async def _truncate_tables():
        await truncate_entities([FinalContract, ContractTemplate, PropertyContract, StoredFile])

    async def test_create_property_contract(self):
        await create_contract_template(create_contract_template_dto)

        property_contract = await property_contract_service.create_property_contract(create_property_contract_dto)
        self.assertEqual(settings.GOOGLE_DOC_PROPERTY_CONTRACT_FOLDER_ID, property_contract)

    async def test_get_property_contract(self):
        created_property_contract_dto = await create_property_contract(create_property_contract_dto)

        property_contract = await property_contract_service.get_property_contract(created_property_contract_dto.id)

        self.assertEqual(created_property_contract_dto.title, property_contract.title)

    async def test_get_seller_property_contract_page(self):
        await create_property_contract(create_property_contract_dto)

        search_dto = SearchPropertyContractDto(page=0, page_size=10)
        property_contracts = await property_contract_service.get_seller_property_contract_page(search_dto)

        self.assertEqual(1, len(property_contracts.data))
        self.assertEqual(1, property_contracts.total)

    async def test_update_property_contract(self):
        created_property_contract_dto = await create_property_contract(create_property_contract_dto)

        update_dto = UpdatePropertyContractDto(
            title="updated title",
            description="Updated description",
        )

        property_contracts = await property_contract_service.update_property_contract(
            created_property_contract_dto.id,
            update_dto
        )

        self.assertEqual(update_dto.title, property_contracts.title)

    async def test_generate_final_contract(self):
        created_property_contract_dto = await create_property_contract(create_property_contract_dto)
        buyer_id = "buyer_id"
        variables = {}
        contract_amount = Money(value=Decimal(3_000_000), currency=TransactionCurrency.NGN)

        upload_file = create_mock_upload_file()
        store_key = "contracts/hjkhksd87988dddhd8.pdf"

        def mock__generate_s3_key(contract_id: str, buyer_id: str = None):
            return store_key

        self.monkeypatch.setattr(property_contract_service, "_generate_s3_key", mock__generate_s3_key)

        mock_document_storage_provider(
            monkeypatch=self.monkeypatch,
            _s3_key=store_key,
            _bucket=settings.AWS_S3_PROPERTY_BUCKET,
            _local_path=self.local_pdf_path,
            _file_bytes=upload_file.file,
            _metadata={},
            called_methods={},
            response="upload_response",
            validate=False)

        final_contract = await property_contract_service.generate_final_contract(
            created_property_contract_dto.property_id,
            ContractType.SALE_AGREEMENT,
            buyer_id,
            contract_amount,
            variables
        )

        self.assertEqual(created_property_contract_dto.property_id, final_contract.property_id)
        self.assertEqual(buyer_id, final_contract.buyer_id)

    async def test_soft_delete_property_contract(self):
        created_property_contract_dto = await create_property_contract(create_property_contract_dto)

        delete_response = await property_contract_service.soft_delete_property_contract(
            created_property_contract_dto.id)

        self.assertEqual(True, delete_response)
