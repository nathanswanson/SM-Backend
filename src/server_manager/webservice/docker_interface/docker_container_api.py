"""
docker_container_api.py

Docker Container API for managing Docker containers

Author: Nathan Swanson
"""

from __future__ import annotations

import asyncio
import logging
import socket
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import aiodocker
from fastapi import HTTPException

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from aiodocker.containers import DockerContainer

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
    async with docker_container(name) as container:
        if container:
            await container.stop()
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


def docker_port_is_free(port: int) -> bool:
    """check if a port is free"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def _convert_ports(ports: dict[str, int | None]) -> dict[str, list[dict[str, str]] | None]:
    """convert ports to docker format"""
    values: dict[str, list[dict[str, str]] | None] = {}
    for int_port, out_port in ports.items():
        values[int_port] = [{"HostPort": str(out_port)}] if out_port else [{}]
    return values


async def docker_container_create(
    container_name: str, image_name: str, ports: dict[str, int | None] | None, env: dict[str, str] | None
) -> bool:
    """create a new container from an image"""
    async with docker_client() as client:
        try:
            container_args = {
                "Image": image_name,
                "Tty": True,
                "OpenStdin": True,
            }
            if ports:
                container_args["HostConfig"] = {"PortBindings": _convert_ports(ports)}
            else:
                container_args["HostConfig"] = {"PublishAllPorts": True}

            if env:
                env_string: list[str] = []
                for item_key, item_val in env.items():
                    env_string.append(f"{item_key}={item_val}")
                container_args["Env"] = env_string
            container = await client.containers.create(name=container_name, config=container_args)
            await container.start()
        except aiodocker.exceptions.DockerError:
            return False
        else:
            return True


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
    container: DockerContainer = await client.containers.get(container_name)
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
                            logging.debug("Stream for %s cancelled", container_name)
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
