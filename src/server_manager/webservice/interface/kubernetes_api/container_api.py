from typing import override

from server_manager.webservice.db_models import ServersCreate, TemplatesCreate
from server_manager.webservice.interface.interface import ControllerContainerInterface
from server_manager.webservice.logger import sm_logger

namespace = "game-servers"


class KubernetesContainerAPI(ControllerContainerInterface):
    @override
    async def start(self, container_name: str) -> bool:
        return True

    @override
    async def stop(self, container_name: str) -> bool:
        sm_logger.info(f"Stopping container {container_name} in Kubernetes")
        # set k8 deployment to replicas=0
        return True

    @override
    async def remove(self, container_name: str) -> bool:
        return True

    @override
    async def exists(self, container_name: str) -> bool:
        return True

    @override
    async def create(self, server: ServersCreate, template: TemplatesCreate) -> bool:
        return True

    @override
    async def is_running(self, container_name: str) -> bool:
        return True

    @override
    async def health_status(self, container_name: str) -> str | None:
        return "True"

    @override
    async def command(self, container_name: str, command: str) -> bool:
        return True
