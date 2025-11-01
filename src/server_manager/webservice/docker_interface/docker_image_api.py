"""
docker_image_api.py

Docker Image API for managing Docker images

Author: Nathan Swanson
"""

from __future__ import annotations

import aiodocker

from server_manager.webservice.util.context_provider import docker_client


async def docker_image_exposed_port(image_name: str) -> list[int] | None:
    """get exposed port from a docker image"""
    async with docker_client() as client:
        try:
            image = await client.images.get(image_name)
        except aiodocker.DockerError:
            await client.images.pull(image_name, tag="latest")
            image = await client.images.get(image_name)
    exposed_ports = image.get("Config", {}).get("ExposedPorts")
    if exposed_ports:
        # Return all exposed ports as a list of integers
        return [int(port.split("/")[0]) for port in exposed_ports]
    return None


async def docker_get_image_exposed_volumes(image_name: str) -> list[str] | None:
    """get exposed volumes from a docker image"""
    async with docker_client() as client:
        try:
            image = await client.images.get(image_name)
        except aiodocker.DockerError:
            await client.images.pull(image_name, tag="latest")
            image = await client.images.get(image_name)
    exposed_volumes = image.get("Config", {}).get("Volumes")
    return list(exposed_volumes.keys() or [])
