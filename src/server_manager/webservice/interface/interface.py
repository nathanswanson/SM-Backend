from abc import ABCMeta, abstractmethod
from collections.abc import AsyncGenerator

from pydantic import BaseModel, ConfigDict, Field

from server_manager.webservice.db_models import ServersCreate, Templates
from server_manager.webservice.models import Metrics

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
    async def list_directory(self, deployment_name: str, namespace: str, path: str, username: str) -> DirList | None:
        pass

    @abstractmethod
    async def read_file(self, deployment_name: str, namespace: str, path: str, username: str) -> AsyncGenerator:
        pass

    @abstractmethod
    async def read_archive(self, deployment_name: str, namespace: str, path: str, username: str) -> AsyncGenerator:
        pass

    @abstractmethod
    async def write_file(self, deployment_name: str, namespace: str, path: str, data: bytes, username: str) -> bool:
        pass

    @abstractmethod
    async def delete_file(self, deployment_name: str, namespace: str, path: str, username: str) -> bool:
        pass


class ControllerContainerInterface(metaclass=ABCMeta):
    @abstractmethod
    async def create(self, server: ServersCreate, template: Templates, tenant_id: int) -> bool:
        pass

    @abstractmethod
    async def start(self, deployment_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def stop(self, deployment_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def remove(self, deployment_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def exists(self, deployment_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def is_running(self, deployment_name: str, namespace: str) -> bool:
        pass

    @abstractmethod
    async def health_status(self, deployment_name: str, namespace: str) -> str | None:
        pass

    @abstractmethod
    async def command(self, deployment_name: str, command: str, namespace: str) -> bool:
        pass


class ControllerStreamingInterface(metaclass=ABCMeta):
    """Interface for streaming logs and metrics from containers."""

    @abstractmethod
    def stream_logs(
        self, deployment_name: str, namespace: str, tail: int = 100, follow: bool = True
    ) -> AsyncGenerator[str, None]:
        """Stream logs from a container.

        Args:
            deployment_name: Name of the container/pod
            namespace: Namespace of the container
            tail: Number of historical lines to fetch
            follow: Whether to follow new logs

        Yields:
            Log lines as strings
        """
        ...

    @abstractmethod
    def stream_metrics(self, deployment_name: str, namespace: str) -> AsyncGenerator[Metrics, None]:
        """Stream metrics from a container.

        Args:
            deployment_name: Name of the container/pod
            namespace: Namespace of the container

        Yields:
            Metrics objects with cpu, memory, disk, network stats
        """
        ...
