"""
docker_container_api.py

Docker Container API for managing Docker containers

Author: Nathan Swanson
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import aiodocker
from fastapi import HTTPException

from server_manager.webservice.docker_interface.docker_image_api import docker_get_image_exposed_volumes

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from aiodocker.containers import DockerContainer

from pydantic import BaseModel, ConfigDict, Field

from server_manager.webservice.logger import sm_logger

banned_container_access = ["server-manager", "rproxy", "docker-socket-proxy", "postgres", "postgres_admin"]


@dataclass
class Message:
    room: str
    data: str
    event_type: str = "push_log"


@dataclass
class Provider:
    task_log: asyncio.Task
    task_metric: asyncio.Task

    def cancel_all(self):
        self.task_log.cancel()
        self.task_metric.cancel()


@asynccontextmanager
async def docker_client():
    client = aiodocker.Docker()
    try:
        yield client
    finally:
        await client.close()


@asynccontextmanager
async def docker_container(container: str):
    async with docker_client() as client:
        try:
            yield client.containers.container(container)
        except aiodocker.exceptions.DockerError:
            return


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
                "NetworkingConfig": {"EndpointsConfig": {"builder_servers": {}}},  # TODO: not called builder_*
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
            if len(health_logs) == 0:
                return None
            health_data = info["State"]["Health"]["Log"][-1]
            return HealthInfo.model_validate(health_data)
    return None


async def docker_container_metrics(container_name: str) -> AsyncGenerator[str]:
    """stream metrics from a container"""
    if container_name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    async with docker_container(container_name) as container:
        if container:
            async for stat in container.stats():
                try:
                    yield (
                        str(
                            [
                                round(_cpu_percent(stat), 4),
                                round(stat["memory_stats"]["usage"] / stat["memory_stats"]["limit"], 4),
                                stat["networks"]["eth0"]["rx_bytes"],
                                stat["networks"]["eth0"]["tx_bytes"],
                                stat["blkio_stats"]["io_service_bytes_recursive"][0]["value"],
                                stat["blkio_stats"]["io_service_bytes_recursive"][1]["value"],
                            ]
                        )
                    )
                except KeyError:
                    yield str([0, 0, 0, 0, 0, 0])
                await asyncio.sleep(5)


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


def _cpu_percent(metric: dict[str, Any]) -> float:
    """calculate cpu percentage from a metric"""
    try:
        cpu_stats = metric.get("cpu_stats", {})
        precpu_stats = metric.get("precpu_stats", {})

        total_usage_current = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        total_usage_prev = precpu_stats.get("cpu_usage", {}).get("total_usage", 0)

        total_system_current = cpu_stats.get("system_cpu_usage", 0)
        total_system_prev = precpu_stats.get("system_cpu_usage", 0)

        cpu_delta = total_usage_current - total_usage_prev
        system_delta = total_system_current - total_system_prev

        if system_delta <= 0 or cpu_delta <= 0:
            return 0.0

        # Prefer reported online_cpus, fall back to percpu_usage length, then to 1
        online_cpus = cpu_stats.get("online_cpus")
        if not online_cpus:
            percpu = cpu_stats.get("cpu_usage", {}).get("percpu_usage") or []
            online_cpus = len(percpu) or 1

        return (cpu_delta / system_delta) * float(online_cpus) * 100.0
    except KeyError:
        return 0.0


async def docker_container_logs_tail(container_name: str, tail: int) -> list[str]:
    """get the last n lines of logs from a container"""
    if container_name in banned_container_access:
        raise HTTPException(status_code=403, detail="Access to container denied")
    client = aiodocker.Docker()
    try:
        container: DockerContainer = await client.containers.get(container_name)
    except aiodocker.DockerError as e:
        sm_logger.error("Failed to Find docker container %s", container_name)
        raise HTTPException(status_code=404, detail=f"Failed to find container '{container_name }'") from e
    logs = await container.log(tail=tail, stdout=True, stderr=True)
    lines: list[str] = []
    for chunk in logs:
        lines.extend(chunk.splitlines())
    await client.close()
    return lines


async def docker_container_logs(container_name: str) -> Any:
    """stream logs from a container"""
    async with docker_container(container_name) as container:
        if container:
            log_buffer = ""
            # TODO: timeout error fix
            async for chunk in container.log(stdout=True, stderr=True, follow=True):
                log_buffer += chunk
                while "\n" in log_buffer:
                    line, log_buffer = log_buffer.split("\n", 1)
                    yield line + "\n"


async def merge_streams() -> AsyncGenerator[Message, None]:
    """merge logs and metrics from all containers"""
    queue = asyncio.Queue(maxsize=100)

    async def __monitor_all_containers():
        tasks: dict[str, Provider] = {}

        async with docker_client() as client:
            while True:
                running_containers = {_extract_common_name(c): c for c in await client.containers.list()}

                # Start monitoring for new containers
                for name in set(running_containers.keys()) - set(tasks.keys()):
                    if name in banned_container_access:
                        continue

                    async def enqueue_stream(stream, container_name, command: str):
                        try:
                            async for msg in stream(container_name):
                                await queue.put(Message(data=msg, room=f"01+{container_name}", event_type=command))
                        except asyncio.CancelledError:
                            sm_logger.debug("Stream for %s cancelled", container_name)
                            if container_name in tasks:
                                tasks.pop(container_name).cancel_all()

                    provider = Provider(
                        asyncio.create_task(enqueue_stream(docker_container_metrics, name, "push_metric")),
                        asyncio.create_task(enqueue_stream(docker_container_logs, name, "push_log")),
                    )
                    tasks[name] = provider

                # Stop monitoring for containers that are no longer running
                for name in set(tasks.keys()) - set(running_containers.keys()):
                    if name in tasks:
                        tasks.pop(name).cancel_all()

                await asyncio.sleep(5)

    _ref = [asyncio.create_task(__monitor_all_containers())]

    async def consumer_generator():
        while True:
            yield await queue.get()

    return consumer_generator()
