from typing import Dict

from _pytest.monkeypatch import MonkeyPatch
from kink import di

from main.app.config.settings import settings
from main.app.domain.property.contract.models import CreatePropertyContractDto, SearchPropertyContractDto
from main.app.domain.property.contract.service import PropertyContractService
from main.app.domain.property.contract.template.models import CreateContractTemplateDto, ContractType, PropertyType
from main.app.domain.property.contract.template.service import ContractTemplateService
from main.appodus_utils.integrations.document_storage import IDocumentStorageProvider
from main.appodus_utils.integrations.document_storage.factory import DocumentStorageProviderFactory
from main.appodus_utils.integrations.google_drive.google_drive_client import GoogleDriveClient
from main.app.utils.decorators.transactional import transactional, TransactionSessionPolicy

contract_template_service: ContractTemplateService = di[ContractTemplateService]
property_contract_service: PropertyContractService = di[PropertyContractService]
create_contract_template_dto = CreateContractTemplateDto(title="title", description="description", country="Nigeria",
    state="Lagos", contract_type=ContractType.SALE_AGREEMENT)
create_property_contract_dto = CreatePropertyContractDto(title="title", description="description", country="Nigeria",
    state="Lagos", contract_types=[ContractType.SALE_AGREEMENT], property_id="property_id", seller_id="seller_id",
    seller_google_email="kingsley.ezenwere@gmail.com", property_type=PropertyType.LAND)


@transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
async def create_contract_template(_create_contract_template_dto: CreateContractTemplateDto):
    return await contract_template_service.create_contract_template(_create_contract_template_dto)


@transactional(session_policy=TransactionSessionPolicy.ALWAYS_NEW)
async def create_property_contract(_create_property_contract_dto: CreatePropertyContractDto):
    await create_contract_template(create_contract_template_dto)
    await property_contract_service.create_property_contract(_create_property_contract_dto)
    search_dto: SearchPropertyContractDto = SearchPropertyContractDto(page=0, page_size=1)
    response = await property_contract_service.get_seller_property_contract_page(search_dto)
    if len(response.data) > 0:
        return response.data[0]

    return None


def mock_google_drive_client(monkeypatch: MonkeyPatch, _file_id: str, _new_name: str, _email: str = None, _pdf_path: str = None):
    google_drive_client: GoogleDriveClient = di[GoogleDriveClient]

    # copy_file
    async def mock_copy_file(file_id: str, new_name: str, parent_folder_id: str = None):
        assert file_id == _file_id

        return {'id': settings.GOOGLE_DOC_PARENT_CONTRACT_ID, 'name': new_name, 'webViewLink': 'new_doc_id_webViewLink'}

    monkeypatch.setattr(google_drive_client, "copy_file", mock_copy_file)

    # set_permissions
    async def mock_set_permissions(file_id: str, email: str):
        assert file_id == _file_id
        assert email == _email

    monkeypatch.setattr(google_drive_client, "set_permissions", mock_set_permissions)

    # create_or_get_folder
    async def mock_create_or_get_folder(name: str, parent_id: str = None):
        return {'id': settings.GOOGLE_DOC_PROPERTY_CONTRACT_FOLDER_ID, 'name': name, }

    monkeypatch.setattr(google_drive_client, "create_or_get_folder", mock_create_or_get_folder)

    # update_placeholders
    async def mock_update_placeholders(file_id: str, replacements: Dict[str, str]):
        return []

    monkeypatch.setattr(google_drive_client, "update_placeholders", mock_update_placeholders)

    # export_to_pdf
    async def mock_export_to_pdf(file_id: str, pdf_path: str):
        return _pdf_path

    monkeypatch.setattr(google_drive_client, "export_to_pdf", mock_export_to_pdf)
