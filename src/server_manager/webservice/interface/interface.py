from abc import abstractmethod
from collections.abc import AsyncGenerator

from pydantic import BaseModel, ConfigDict, Field

type DirList = tuple[list[str], list[str]]


class HealthInfo(BaseModel):
    model_config = ConfigDict(strict=True)

    start: str = Field(alias="Start")
    end: str = Field(alias="End")
    exit_code: int = Field(alias="ExitCode")
    output: str = Field(alias="Output")


class ControllerImageInterface:
    @staticmethod
    @abstractmethod
    def image_exposed_port(image_name: str) -> list[int] | None:
        pass

    @staticmethod
    @abstractmethod
    def image_exposed_volumes(image_name: str) -> list[str] | None:
        pass


class ControllerVolumeInterface:
    @staticmethod
    @abstractmethod
    def list_directory(container_name: str, path: str) -> DirList | None:
        pass

    @staticmethod
    @abstractmethod
    def read_file(container_name: str, path: str) -> AsyncGenerator:
        pass

    @staticmethod
    @abstractmethod
    def read_archive(container_name: str, path: str) -> AsyncGenerator:
        pass

    @staticmethod
    @abstractmethod
    def write_file(container_name: str, path: str, data: bytes) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def delete_file(container_name: str, path: str) -> bool:
        pass


class ControllerContainerInterface:
    @staticmethod
    @abstractmethod
    def list_container_names() -> list[dict]:
        pass

    @staticmethod
    @abstractmethod
    def get_container(container_name: str) -> dict | None:
        pass

    @staticmethod
    @abstractmethod
    def create_container(container_config: dict) -> dict:
        pass

    @staticmethod
    @abstractmethod
    def start_container(container_name: str) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def stop_container(container_name: str) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def remove_container(container_name: str) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def container_name_exists(container_name: str) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def container_running(container_name: str) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def container_health_status(container_name: str) -> str | None:
        pass

    @staticmethod
    @abstractmethod
    def container_inspect(container_name: str) -> dict | None:
        pass

    @staticmethod
    @abstractmethod
    def container_command(container_name: str, command: str) -> bool:
        pass
