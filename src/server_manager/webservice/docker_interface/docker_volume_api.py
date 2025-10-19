"""
docker_volume_api.py

Docker Volume API for managing files within Docker containers

Author: Nathan Swanson
"""

import os
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from aiodocker import DockerError

from server_manager.webservice.docker_interface.docker_container_api import docker_container

if TYPE_CHECKING:
    from io import BytesIO


async def docker_list_directory(container_name: str, path: str) -> tuple[list[str], list[str]] | None:
    """list files in a directory inside a container"""
    async with docker_container(container_name) as container:
        if container:
            exec_log_files = await container.exec(["find", path, '-maxdepth','1','-type', 'f', '-printf', '%P\n'], workdir="/")
            exec_log_dirs = await container.exec(["find", path, '-maxdepth','1','-type', 'd', '-printf', '%P\n'], workdir="/")
            response_files = await exec_log_files.start().read_out()
            response_dirs = await exec_log_dirs.start().read_out()
            if response_files and response_dirs:
                files = response_files.data.decode("utf-8").split()
                dirs = response_dirs.data.decode("utf-8").split()
                return files, dirs
    return None


async def docker_read_file(container_name: str, path: str) -> AsyncGenerator:
    """read a file from a container"""
    async with docker_container(container_name) as container:
        file = await container.get_archive(path)
        if file and file.fileobj:
            buffer: BytesIO = file.fileobj  # type: ignore
            file_size = file.getmembers()[0].size if file.getmembers() else 0
            offset = file.getmembers()[0].offset_data if file.getmembers() else 0
            yield file_size.to_bytes(8, "big")
            buffer.seek(offset)
            while (chunk := buffer.read(min(4096, offset + file_size - buffer.tell()))) != b"":
                yield chunk
        else:
            yield -1


async def docker_file_upload(container_name: str, path: str, data: bytes) -> bool:
    """upload a file to a container"""
    async with docker_container(container_name) as container:
        if container:
            print(container)
            try:
                # get dirname
                await container.put_archive(os.path.dirname(path), data)
            except DockerError as e:
                print("Failed to upload file:", e)
            return True
        return False


async def docker_delete_file(container_name: str, path: str) -> bool:
    """delete a file or directory from a container"""
    async with docker_container(container_name) as container:
        if container:
            await container.exec(f"rm -rf {path}")
            return True
    return False


def docker_volume_path(container_name: str, path: str) -> str:
    """get the full path to a file in a container"""
    return f"{os.environ['SM_MOUNT_PATH']}/{container_name}/{path.lstrip('/')}"
