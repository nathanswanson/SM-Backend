from contextlib import asynccontextmanager

import aiodocker


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
