from typing import Any, cast, override

import aiodocker
from aiodocker.containers import DockerContainer
from fastapi import HTTPException

from server_manager.webservice.db_models import ServersCreate, TemplatesCreate
from server_manager.webservice.interface.interface import ControllerContainerInterface, HealthInfo
from server_manager.webservice.util.context_provider import docker_client, docker_container

banned_container_access = ["server-manager", "rproxy", "docker-socket-proxy", "postgres", "postgres_admin"]


class DockerContainerAPI(ControllerContainerInterface):
    @override
    async def create(self, server: ServersCreate, template: TemplatesCreate) -> bool:
        return False

    @override
    async def start(self, container_name: str, namespace: str) -> bool:
        if container_name in banned_container_access:
            raise HTTPException(status_code=403, detail="Access to container denied")
        async with docker_container(container_name) as container:
            if container:
                await container.start()
                return True
            return False
        return False

    @override
    async def stop(self, container_name: str, namespace: str) -> bool:
        if container_name in banned_container_access:
            raise HTTPException(status_code=403, detail="Access to container denied")
        async with docker_container(container_name) as container:
            if container:
                await container.stop()
                return True
            return False
        return False

    @override
    async def is_running(self, container_name: str, namespace: str) -> bool:
        """check if a container is running by name"""
        if container_name in banned_container_access:
            raise HTTPException(status_code=403, detail="Access to container denied")
        async with docker_container(container_name) as container:
            if container:
                info = await container.show()
                return info["State"]["Running"]
            return False
        return False

    @override
    async def health_status(self, container_name: str, namespace: str) -> str | None:
        if container_name in banned_container_access:
            raise HTTPException(status_code=403, detail="Access to container denied")
        health_data = await self._docker_container_inspect(container_name, namespace)
        return health_data.output if health_data else "Health Check N/A"

    async def _docker_container_inspect(self, container_name: str, namespace: str) -> HealthInfo | None:
        """inspect a container"""
        if container_name in banned_container_access:
            raise HTTPException(status_code=403, detail="Access to container denied")
        if not await self.is_running(container_name, namespace):
            raise HTTPException(status_code=400, detail=f"Container '{container_name}' is not running")

        async with docker_container(container_name) as container:
            if container:
                info = await container.show()
                health_state = info["State"].get("Health") if info and info.get("State") else None
                logs = health_state.get("Log") if health_state else None
                if not logs:
                    return None
                health_data = logs[-1]
                return HealthInfo.model_validate(health_data)
        return None

    @override
    async def command(self, container_name: str, command: str, namespace: str) -> bool:
        """send a command to a container"""
        async with docker_container(container_name) as container:
            # Get the raw socket
            if container:
                attach_result = container.attach(
                    stdin=True,
                    stdout=True,
                    stderr=True,
                )
                sock = attach_result
                if hasattr(attach_result, "__await__"):
                    sock = await cast(Any, attach_result)

                await sock.write_in(f"{command}\n".encode())
                return True
            return False

    @staticmethod
    def _extract_common_name(container: DockerContainer) -> str:
        """extract the common name from a container"""
        return container._container["Names"][0].strip("/")  # noqa: SLF001

    @override
    async def remove(self, container_name: str, namespace: str) -> bool:
        if container_name in banned_container_access:
            raise HTTPException(status_code=403, detail="Access to container denied")
        async with docker_container(container_name) as container:
            if container:
                await container.delete(force=True)
                return True
            return False
        return False

    @override
    async def exists(self, container_name: str, namespace: str) -> bool:
        if container_name in banned_container_access:
            raise HTTPException(status_code=403, detail="Access to container denied")
        async with docker_client() as client:
            try:
                await client.containers.get(container_name)
            except aiodocker.exceptions.DockerError:
                return False
            else:
                return True
