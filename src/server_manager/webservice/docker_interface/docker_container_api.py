from __future__ import annotations

import asyncio
import socket
from contextlib import asynccontextmanager
from math import trunc
from typing import TYPE_CHECKING, Any

import aiodocker

if TYPE_CHECKING:
    from aiodocker.containers import DockerContainer
    from fastapi import Request


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
    async with docker_container(name) as container:
        return container is not None


async def docker_container_stop(name: str) -> bool:
    async with docker_container(name) as container:
        if container:
            await container.stop()
            return True
        return False


async def docker_container_remove(name: str) -> bool:
    async with docker_container(name) as container:
        if container:
            await container.stop()
            await container.delete()
            return True
        return False


async def docker_container_start(name: str) -> bool:
    async with docker_container(name) as container:
        if container:
            await container.start()
            return True
        return False


async def docker_container_running(name: str) -> bool:
    async with docker_container(name) as container:
        if container:
            info = await container.show()
            return info["State"]["Running"]
        return False


def _extract_common_name(container: DockerContainer) -> str:
    return container._container["Names"][0].strip("/")  # noqa: SLF001


async def docker_list_containers_names() -> list[str]:
    async with docker_client() as client:
        containers = await client.containers.list(all=True)
        return [_extract_common_name(container) for container in containers]


async def docker_container_get(name: str) -> DockerContainer | None:
    async with docker_container(name) as container:
        try:
            return container
        except aiodocker.exceptions.DockerError:
            return None


async def docker_list_containers() -> list[DockerContainer]:
    async with docker_client() as client:
        return await client.containers.list(all=True)


async def docker_stop_all_containers() -> None:
    async with docker_client() as client:
        containers = await client.containers.list()
        for container in containers:
            await container.stop()


def docker_port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def _convert_ports(ports: dict[str, int | None]) -> dict[str, list[dict[str, str]] | None]:
    values: dict[str, list[dict[str, str]] | None] = {}
    for int_port, out_port in ports.items():
        values[int_port] = [{"HostPort": str(out_port)}] if out_port else [{}]
    return values


async def docker_container_create(
    container_name: str, image_name: str, ports: dict[str, int | None] | None, env: dict[str, str] | None
) -> bool:
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


async def docker_container_metrics(name: str, request: Request):  # noqa: ARG001
    async with docker_container(name) as container:
        if container:
            async for stat in container.stats():
                # cpu_per, mem_usage_per, net_up_byte, net_down_byte, block_up_byte, block_down_byte
                yield (
                    [
                        _cpu_percent(stat),
                        round(stat["memory_stats"]["usage"] / stat["memory_stats"]["limit"], 2),
                        stat["networks"]["eth0"]["rx_bytes"],
                        stat["networks"]["eth0"]["tx_bytes"],
                        stat["blkio_stats"]["io_service_bytes_recursive"][0]["value"],
                        stat["blkio_stats"]["io_service_bytes_recursive"][1]["value"],
                    ]
                )
                await asyncio.sleep(10)


def _cpu_percent(metric: dict[str, Any]) -> float:
    total_usage_current = metric["cpu_stats"]["cpu_usage"]["total_usage"]
    total_usage_prev = metric["precpu_stats"]["cpu_usage"]["total_usage"]
    total_system_current = metric["cpu_stats"]["system_cpu_usage"]

    total_system_prev = metric["precpu_stats"].get("system_cpu_usage", 0)
    cpu_percent = (total_usage_current - total_usage_prev) / (total_system_current - total_system_prev) * 100
    return trunc(cpu_percent * 100) / 100


async def docker_container_send_command(name: str, command: str):
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


async def docker_container_logs(name: str, request: Request):  # noqa: ARG001
    async with docker_container(name) as container:
        if container:
            log_line = ""
            async for log in container.log(stdout=True, follow=True):
                for char in log:
                    log_line += char
                    if char == "\n":
                        yield log_line
                        log_line = ""
