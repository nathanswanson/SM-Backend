"""
docker_container_api.py

Docker Container API for managing Docker containers

Author: Nathan Swanson
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import aiodocker
from fastapi import HTTPException

from server_manager.webservice.docker_interface.docker_image_api import docker_get_image_exposed_volumes
from server_manager.webservice.util.context_provider import docker_client, docker_container

if TYPE_CHECKING:
    from aiodocker.containers import DockerContainer


from pydantic import BaseModel, ConfigDict, Field

from server_manager.webservice.logger import sm_logger

SSE_KEEP_ALIVE_INTERVAL = 5  # seconds

banned_container_access = ["server-manager", "rproxy", "docker-socket-proxy", "postgres", "postgres_admin"]


async def docker_container_name_exists(name: str) -> bool:
    """check if a container name exists"""
    if name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    async with docker_container(name) as container:
        return container is not None


async def docker_container_stop(name: str) -> bool:
    """stop a container by name"""
    if name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    async with docker_container(name) as container:
        if container:
            await container.stop()
            return True
        return False


async def docker_container_remove(name: str) -> bool:
    """remove a container by name"""
    if name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    if await docker_container_running(name):
        await docker_container_stop(name)
    async with docker_container(name) as container:
        if container:
            await container.delete()
            return True
        return False


async def docker_container_start(name: str) -> bool:
    """start a container by name"""
    if name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    async with docker_container(name) as container:
        if container:
            await container.start()
            return True
        return False
    return False


async def docker_exposed_ports(name: str) -> list[int]:
    """get a list of exposed ports from a container by name"""
    if name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    async with docker_container(name) as container:
        if container:
            info = await container.show()
            ports = info["NetworkSettings"]["Ports"]
            exposed_ports: list[int] = []
            for mappings in ports.values():
                if mappings:
                    try:
                        exposed_ports.append(int(mappings[0]["HostPort"]))
                    except (ValueError, KeyError, TypeError):
                        continue
            return exposed_ports
        return []


async def docker_container_running(name: str) -> bool:
    """check if a container is running by name"""
    if name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    async with docker_container(name) as container:
        if container:
            info = await container.show()
            return info["State"]["Running"]
        return False
    return False


def _extract_common_name(container: DockerContainer) -> str:
    """extract the common name from a container"""
    return container._container["Names"][0].strip("/")  # noqa: SLF001


async def docker_list_containers_names() -> list[str]:
    """list all container names"""
    async with docker_client() as client:
        containers = await client.containers.list(all=True)
        return [
            _extract_common_name(container)
            for container in containers
            if _extract_common_name(container) not in banned_container_access
        ]


async def docker_stop_all_containers() -> None:
    """stop all containers"""
    async with docker_client() as client:
        containers = await client.containers.list()
        for container in containers:
            await container.stop()


async def map_image_volumes(image_name: str, container_name: str) -> list[str]:
    """map image volumes to host volumes"""
    exposed_volumes = await docker_get_image_exposed_volumes(image_name)
    mount_path = os.environ.get("SM_MOUNT_PATH", "/mnt/server_manager")
    if exposed_volumes:
        return [f"{os.path.abspath(mount_path)}/{container_name}{vol}:{vol}" for vol in exposed_volumes]
    return []


def _get_servers_network_name() -> str:
    """get the servers network name"""
    return subprocess.run(
        ["/usr/bin/docker", "network", "ls", "--filter", "name=_servers$", "--format", "{{.Name}}"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()


async def docker_container_create(
    container_name: str,
    image_name: str,
    env: dict[str, str] | None,
    server_link: str | None = None,
    user_link: str | None = None,
) -> bool:
    """create a new container from an image"""

    async with docker_client() as client:
        try:
            container_args = {
                "Image": image_name,
                "Tty": True,
                "OpenStdin": True,
                "NetworkingConfig": {"EndpointsConfig": {_get_servers_network_name(): {}}},
                "HostConfig": {"Binds": await map_image_volumes(image_name, container_name)},
            }

            if server_link:
                container_args["Labels"] = {"online.nathanswanson.server_link": server_link}

            if user_link:
                if "Labels" not in container_args:
                    container_args["Labels"] = {}
                container_args["Labels"]["online.nathanswanson.user_link"] = user_link
            if env:
                env_string: list[str] = []
                for item_key, item_val in env.items():
                    env_string.append(f"{item_key}={item_val}")
                container_args["Env"] = env_string
            # create the folders for the volumes
            for volume in container_args["HostConfig"]["Binds"]:
                host_path = volume.split(":")[0]
                os.makedirs(host_path, exist_ok=True)
                if not os.access(host_path, os.W_OK):
                    sm_logger.error(f"Volume path {host_path} is not writable. Please check permissions.")
                    return False
            await client.containers.create(name=container_name, config=container_args)
        except aiodocker.exceptions.DockerError:
            return False
        else:
            return True


class HealthInfo(BaseModel):
    model_config = ConfigDict(strict=True)

    start: str = Field(alias="Start")
    end: str = Field(alias="End")
    exit_code: int = Field(alias="ExitCode")
    output: str = Field(alias="Output")


async def docker_container_health_status(container_name: str) -> str:
    """get the health status of a container"""
    if container_name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    health_data = await docker_container_inspect(container_name)
    return health_data.output if health_data else "Health Check N/A"


async def docker_container_inspect(container_name: str) -> HealthInfo | None:
    """inspect a container"""
    if container_name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    if not await docker_container_running(container_name):
        raise HTTPException(status_code=400, detail=f"Container '{container_name}' is not running")

    async with docker_container(container_name) as container:
        if container:
            info = await container.show()
            health_logs = info["State"].get("Health")
            if not health_logs or not len(health_logs):
                return None
            health_data = info["State"]["Health"]["Log"][-1]
            return HealthInfo.model_validate(health_data)
    return None


async def docker_container_send_command(name: str, command: str):
    """send a command to a container"""
    async with docker_container(name) as container:
        # Get the raw socket
        if container:
            sock = container.attach(
                stdin=True,
                stdout=True,
                stderr=True,
            )

            await sock.write_in(f"{command}\n".encode())
            return True
        return False
