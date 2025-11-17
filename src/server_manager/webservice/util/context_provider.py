from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiodocker
from aiodocker.containers import DockerContainer
from fastapi import HTTPException


@asynccontextmanager
async def docker_client():
    client = aiodocker.Docker()
    try:
        yield client
    finally:
        await client.close()


@asynccontextmanager
async def docker_container(container: str) -> AsyncGenerator[DockerContainer, None]:
    try:
        async with docker_client() as client:
            yield await client.containers.get(container)

    except aiodocker.exceptions.DockerError as e:
        raise HTTPException(status_code=404, detail=f"Container {container} not found") from e
