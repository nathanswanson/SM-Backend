"""
docker_image_api.py

Docker Image API for managing Docker images

Author: Nathan Swanson
"""

from __future__ import annotations

import aiodocker
from fastapi.concurrency import asynccontextmanager


@asynccontextmanager
async def docker_client():
    client = aiodocker.Docker()
    try:
        yield client
    finally:
        await client.close()


async def docker_get_image_exposed_volumes(image_name: str) -> list[str] | None:
    """get exposed volumes from a docker image"""
    async with docker_client() as client:
        try:
            image = await client.images.get(image_name)
        except aiodocker.DockerError:
            return None
    exposed_volumes = image.get("Config", {}).get("Volumes")
    return list(exposed_volumes.keys() or [])
