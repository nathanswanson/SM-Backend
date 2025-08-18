from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import docker
import docker.errors

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
    container.stop()
    container.remove()
    return True


def docker_container_running(container: Container) -> bool:
    return container.status == "running"


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
