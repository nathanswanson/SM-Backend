from abc import ABCMeta, abstractmethod
from collections.abc import AsyncGenerator

from pydantic import BaseModel, ConfigDict, Field

from server_manager.webservice.db_models import ServersCreate, Templates

type DirList = tuple[list[str], list[str]]


class HealthInfo(BaseModel):
    model_config = ConfigDict(strict=True)

    start: str = Field(alias="Start")
    end: str = Field(alias="End")
    exit_code: int = Field(alias="ExitCode")
    output: str = Field(alias="Output")


class ControllerImageInterface:
    @abstractmethod
    async def image_exposed_port(self, image_name: str) -> list[int] | None:
        pass

    @abstractmethod
    async def image_exposed_volumes(self, image_name: str) -> list[str] | None:
        pass


class ControllerVolumeInterface:
    @abstractmethod
    async def list_directory(self, container_name: str, namespace: str, path: str) -> DirList | None:
        pass

    @abstractmethod
    async def read_file(self, container_name: str, namespace: str, path: str) -> AsyncGenerator:
        pass

    @abstractmethod
    async def read_archive(self, container_name: str, namespace: str, path: str) -> AsyncGenerator:
        pass

    @abstractmethod
    async def write_file(self, container_name: str, namespace: str, path: str, data: bytes) -> bool:
        pass

    @abstractmethod
    async def delete_file(self, container_name: str, namespace: str, path: str) -> bool:
        pass


class ControllerContainerInterface(metaclass=ABCMeta):
    @abstractmethod
    async def create(self, server: ServersCreate, template: Templates) -> bool:
        pass

    @abstractmethod
    async def start(self, container_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def stop(self, container_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def remove(self, container_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def exists(self, container_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def is_running(self, container_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def health_status(self, container_name: str, namespace: str) -> str | None:
        pass

    @abstractmethod
    async def command(self, container_name: str, command: str, namespace: str) -> bool:
        pass
