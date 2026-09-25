from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from loguru import Logger

from fastapi import HTTPException
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from kink import di, inject

from main.app.config.settings import settings

logger: Logger = di['logger']


def _drive_failure(action: str, error: HttpError) -> HTTPException:
    """The exception to raise when a Google call fails.

    Google's error text names our service account, file ids and quota details; it goes to the
    log, and the response says only which step failed. The status is Google's, as before.
    """
    logger.error(f"Google API call failed to {action}: {error}")
    return HTTPException(status_code=error.status_code, detail=f"Could not {action} in Google Drive.")


@inject
class GoogleDriveClient:
    def __init__(self):
        self.SCOPES = ['https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/drive']
        # TODO: Consider using Workload Identity Federation instead of this Service key file
        self.service_account_file = settings.GOOGLE_SERVICE_ACCOUNT_FILE
        self.credentials = service_account.Credentials.from_service_account_file(self.service_account_file,
                                                                                 scopes=self.SCOPES)

        self._docs_service = build('docs', 'v1', credentials=self.credentials)
        self._drive_service = build('drive', 'v3', credentials=self.credentials)

    async def create_or_get_folder(self, name: str, parent_folder_id: str = None):
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        try:
            # Step 1: Search for existing folder
            response = await asyncio.to_thread(
                lambda: self._drive_service.files().list(q=query, spaces='drive', fields='files(id, name)',
                                                         supportsAllDrives=True,
                                                         includeItemsFromAllDrives=True).execute())

            if response['files']:
                # Step 2: Folder exists, return the first match
                return response['files'][0]

            # Step 3: Folder not found, create it
            metadata = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
            if parent_folder_id:
                metadata['parents'] = [parent_folder_id]

            result = await asyncio.to_thread(
                lambda: self._drive_service.files().create(body=metadata, fields='id, name',
                                                           supportsAllDrives=True).execute())

            return result

        except HttpError as error:
            raise _drive_failure("create or find the folder", error) from error

    async def copy_file(self, file_id: str, new_name: str, parent_folder_id: str = None):
        body = {'name': new_name}
        if parent_folder_id:
            body['parents'] = [parent_folder_id]

        try:
            result = await asyncio.to_thread(
                lambda: self._drive_service.files().copy(fileId=file_id, body=body, supportsAllDrives=True,
                                                         fields='id,name,webViewLink').execute())
            return result
        except HttpError as error:
            raise _drive_failure("copy the file", error) from error

    async def set_permissions(self, file_id: str, email: str, role: str = 'writer'):
        try:
            permission = {'type': 'user', 'role': role, 'emailAddress': email}
            result = await asyncio.to_thread(
                lambda: self._drive_service.permissions().create(fileId=file_id, body=permission,
                                                                 fields='id').execute())
            return result
        except HttpError as error:
            raise _drive_failure("set file permissions", error) from error

    async def export_to_pdf(self, file_id: str, output_path: str):
        try:
            request = self._drive_service.files().export_media(fileId=file_id, mimeType='application/pdf')
            with open(output_path, 'wb') as f:
                f.write(request.execute())
            return output_path
        except HttpError as error:
            raise _drive_failure("export the file", error) from error

    async def update_placeholders(self, file_id: str, replacements: Dict[str, str]):
        """
        Replace template variables in a Google Doc
        Format: {{variable_name}} in the document
        """
        requests = []

        for variable, value in replacements.items():
            # Find all instances of the variable
            requests.append({'replaceAllText': {'containsText': {'text': f'{{{{{variable}}}}}', 'matchCase': False},
                                                'replaceText': value}})

        try:
            result = await asyncio.to_thread(lambda: self._docs_service.documents().batchUpdate(documentId=file_id,
                                                                                                body={'requests': requests}).execute())
            return result
        except HttpError as error:
            raise _drive_failure("update the document", error) from error

    async def get_document_content(self, file_id: str):
        """Get structured content of a document"""
        try:
            result = await asyncio.to_thread(
                lambda: self._docs_service.documents().get(documentId=file_id).execute())
            return result
        except HttpError as error:
            raise _drive_failure("read the document", error) from error

    async def watch_file_changes(self, file_id: str, channel_id: str, webhook_url: str):
        """Set up a webhook for file changes"""
        try:
            # Create watch request
            channel = {'id': channel_id, 'type': 'web_hook', 'address': webhook_url, 'payload': True,
                       'params': {'ttl': settings.GOOGLE_WEBHOOK_NOTIFICATION_TTL}}
            result = await asyncio.to_thread(
                lambda: self._drive_service.files().watch(fileId=file_id, body=channel).execute())
            return result
        except HttpError as error:
            raise _drive_failure("watch the file", error) from error

    async def stop_watching(self, channel_id: str, resource_id: str):
        """Stop receiving notifications"""
        try:
            channel = {'id': channel_id, 'resourceId': resource_id}
            result = await asyncio.to_thread(lambda: self._drive_service.channels().stop(body=channel).execute())
            return result
        except HttpError as error:
            raise _drive_failure("stop watching the file", error) from error
