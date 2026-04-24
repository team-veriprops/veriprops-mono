from abc import abstractmethod, ABC

from typing_extensions import BinaryIO

from main.app.config.settings import settings


class IDocumentStorageProvider(ABC):
    @property
    @abstractmethod
    def platform(self) -> str:
        pass

    @abstractmethod
    async def upload(self, key: str, bucket: str, file_bytes: BinaryIO, metadata: dict) -> str:
        pass

    @abstractmethod
    async def get_presigned_url(self, key: str, bucket: str,
                                expires_in_sec: int = settings.AWS_S3_PRESIGNED_URL_EXPIRES) -> str:
        pass

    @abstractmethod
    async def upload_local_doc(self, key: str, bucket: str, local_path: str, metadata: dict) -> str:
        pass

    @abstractmethod
    async def delete(self, key: str, bucket: str) -> None:
        pass
