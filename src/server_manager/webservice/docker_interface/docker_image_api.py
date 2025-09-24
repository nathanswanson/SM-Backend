"""
docker_image_api.py

Docker Image API for managing Docker images

Author: Nathan Swanson
"""

from __future__ import annotations

import re

import docker
import docker.errors
from docker.models.images import Image


def docker_get_env_vars(image: Image) -> dict[str, str | None]:
    """get environment variables from a docker image"""
    return {var.split("=")[0]: var.split("=")[1] if "=" in var else None for var in image.attrs["Config"]["Env"]}


def docker_get_image_exposed_ports(image: Image) -> list[str]:
    """get exposed ports from a docker image"""
    exposed_ports = image.attrs["Config"]["ExposedPorts"]
    return list(exposed_ports.keys())


def docker_get_image(image_name: str) -> Image | None:
    """get a docker image by name"""
    client = docker.from_env()
    try:
        return client.images.get(image_name)
    except docker.errors.ImageNotFound:
        return None
    except docker.errors.APIError:
        return None


def docker_get_image_exposed_volumes(image: Image) -> list[str] | None:
    """get exposed volumes from a docker image"""
    exposed_volumes = image.attrs["Config"]["Volumes"]
    if exposed_volumes is None:
        return None
    return list(exposed_volumes.keys())


def docker_image_spawn_container(
    image: Image | str, server_name: str, env: dict[str, str], cpu_count: int = 2, memory_size="2G"
):
    """spawn a container from a docker image"""
    image_obj: Image | None = None
    image_str: str = ""
    if isinstance(image, Image):
        image_obj = image
        image_str = image.tags[0]
    else:
        image_str = image
        image_obj = docker_get_image(image_str) if docker_image_exists(image_str) else docker_pull_image(image_str)

    if image_obj is None:
        return None

    client = docker.from_env()
    container = client.containers.create(
        image=image_str,
        name=server_name,
        environment=env,
        cpu_count=cpu_count,
        mem_limit=memory_size,
        detach=True,
        publish_all_ports=True,
    )
    container.start()
    return container


def docker_pull_image(image_name: str) -> Image | None:
    """pull a docker image by name"""
    client = docker.from_env()
    image: Image | None = None
    try:
        image = client.images.pull(image_name)
    except docker.errors.APIError:
        return None
    else:
        return image


def docker_image_exists(image_name: str) -> bool:
    """check if a docker image exists locally by name"""
    client = docker.from_env()
    try:
        client.images.get(image_name)
    except docker.errors.ImageNotFound:
        return False
    except docker.errors.APIError:
        return False
    else:
        return True


def docker_list_images() -> list[str]:
    """list all docker images by name"""
    client = docker.from_env()
    images = client.images.list()
    return [image.tags[0] for image in images]


def _strip_non_numerals(s: str) -> str:
    """strip non-numerals from a string"""
    return re.sub(r"\D", "", s)
