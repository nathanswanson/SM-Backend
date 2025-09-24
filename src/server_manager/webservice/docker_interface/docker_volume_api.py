"""
docker_volume_api.py

Docker Volume API for managing files within Docker containers

Author: Nathan Swanson
"""

from collections.abc import AsyncGenerator

from server_manager.webservice.docker_interface.docker_container_api import docker_container


async def docker_list_directory(container_name: str, path: str) -> list[str] | None:
    """list files in a directory inside a container"""
    async with docker_container(container_name) as container:
        if container:
            exec_log = await container.exec(["ls", "-p", path], workdir="/")
            response = await exec_log.start().read_out()
            if response:
                return response.data.decode("utf-8").split()
    return None


async def docker_read_file(container_name: str, path: str) -> AsyncGenerator[bytes, None]:
    """read a file from a container"""
    async with docker_container(container_name) as container:
        file = await container.get_archive(path)
        if file:
            file_io = file.fileobj
            # stream file
            if file_io:
                while (chunk := file_io.read(65536)) != b"":
                    yield chunk


async def docker_file_upload(container_name: str, path: str, data: bytes) -> bool:
    """upload a file to a container"""
    async with docker_container(container_name) as container:
        if container:
            await container.put_archive(path, data)
            return True
    return False


async def docker_delete_file(container_name: str, path: str) -> bool:
    """delete a file or directory from a container"""
    async with docker_container(container_name) as container:
        if container:
            await container.exec(f"rm -rf {path}")
            return True
    return False
