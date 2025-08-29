from __future__ import annotations

import asyncio
import logging
import socket
from typing import TYPE_CHECKING

import docker
import docker.errors
from fastapi.responses import StreamingResponse

if TYPE_CHECKING:
    from docker.models.containers import Container


def docker_container_name_exists(container_name: str) -> bool:
    client = docker.from_env()
    try:
        client.containers.get(container_name)
    except docker.errors.NotFound:
        return False
    except docker.errors.APIError:
        return False
    else:
        return True


def docker_stop_container(container: Container) -> bool:
    container.stop()
    # TODO: add timer
    return True


def docker_remove_container(container: Container) -> bool:
    try:
        container.stop()
        container.remove()
    except docker.errors.APIError:
        logging.exception("")
        return False
    else:
        return True


def docker_container_running(container: Container) -> bool:
    return container.status == "running" if container.health == "unknown" else container.health == "healthy"


def docker_start_container(container: Container) -> bool:
    container.start()
    return True


def docker_list_containers_names() -> list[str]:
    client = docker.from_env()
    containers = client.containers.list(all=True)
    return [container.name for container in containers]


def docker_container_get(container_name: str) -> Container | None:
    client = docker.from_env()
    try:
        return client.containers.get(container_name)
    except docker.errors.NotFound:
        return None


def docker_list_containers() -> list[Container]:
    client = docker.from_env()
    return client.containers.list(all=True)


def docker_stop_all_containers() -> None:
    client = docker.from_env()
    containers = client.containers.list()
    for container in containers:
        container.stop()


def docker_port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def docker_container_create(
    container_name: str, image_name: str, ports: dict[str, int] | None, volumes: list[str] | None
) -> bool:
    client = docker.from_env()
    try:
        container = client.containers.create(
            image=image_name, name=container_name, detach=True, ports=ports, volumes=volumes
        )
        container.start()
    except docker.errors.APIError:
        return False
    else:
        return True


async def log_stream(container: Container, line_count: int):
    lines_printed = 0
    logs = container.logs(follow=True, stream=True, stderr=True, stdout=True, tail=line_count)
    for log in logs:
        yield log
        if lines_printed < line_count:
            lines_printed += 1
            await asyncio.sleep(0.1)
        else:
            await asyncio.sleep(1)


def docker_container_logs(container: Container, line_count: int = 1) -> StreamingResponse:
    if not container:
        raise KeyError
    return StreamingResponse(log_stream(container, line_count), media_type="text/plain")
