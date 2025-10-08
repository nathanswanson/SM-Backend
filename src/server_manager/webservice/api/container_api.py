"""
container_api.py

API endpoints for managing Docker containers and their associated volumes.

Author: Nathan Swanson

"""

import io
import os
import tarfile
import zipfile
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from server_manager.webservice.docker_interface.docker_container_api import (
    docker_container_create,
    docker_container_logs_tail,
    docker_container_remove,
    docker_container_running,
    docker_container_send_command,
    docker_container_start,
    docker_container_stop,
    docker_list_containers_names,
)
from server_manager.webservice.docker_interface.docker_volume_api import (
    docker_delete_file,
    docker_file_upload,
    docker_list_directory,
    docker_read_file,
)
from server_manager.webservice.models import (
    ContainerCommandResponse,
    ContainerCreateRequest,
    ContainerCreateResponse,
    ContainerDeleteResponse,
    ContainerFileDeleteResponse,
    ContainerFileListResponse,
    ContainerFileUploadResponse,
    ContainerListResponse,
    ContainerLogsResponse,
    ContainerStartResponse,
    ContainerStatusResponse,
    ContainerStopResponse,
)
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.util import expand_api_url

container = APIRouter(tags=["container"])
metric_data_rate = 10


@container.get(expand_api_url("list"), response_model=ContainerListResponse)
async def list_containers():
    """list all container names"""
    names = await docker_list_containers_names()
    return ContainerListResponse(items=names)


@container.get(expand_api_url("{name}/start"), response_model=ContainerStartResponse)
async def start_container(name: str):
    """start a container by name"""
    ret = await docker_container_start(name)
    return ContainerStartResponse(success=ret)


@container.get(expand_api_url("{name}/stop"), response_model=ContainerStopResponse)
async def stop_container(name: str):
    """stop a container by name"""
    ret = await docker_container_stop(name)
    return ContainerStopResponse(success=ret)


@container.post(expand_api_url("create/{template_name}"), response_model=ContainerCreateResponse)
async def create_container(container_create_req: ContainerCreateRequest):
    """create a new container from a template"""
    template = DB().get_template_by_name(container_create_req.template)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    ret = await docker_container_create(
        container_create_req.server_name, template.image, container_create_req.port, container_create_req.env
    )
    return ContainerCreateResponse(success=ret)


@container.get(expand_api_url("{container_name}/status"), response_model=ContainerStatusResponse)
async def get_container_status(container_name: str):
    """get container running status"""
    is_running = await docker_container_running(container_name)
    return ContainerStatusResponse(running=is_running)


@container.get(expand_api_url("{container_name}/logs"), response_model=ContainerLogsResponse)
async def get_log_message(container_name: str, line_count: int | None = None) -> ContainerLogsResponse:
    """get the last line_count lines of container logs, defaults to 25 if not specified"""
    ret = await docker_container_logs_tail(container_name, tail=line_count or 25)
    return ContainerLogsResponse(items=ret if ret else [])


# Volume
@container.get(expand_api_url("{container_name}/fs/list"), response_model=ContainerFileListResponse)
async def get_directory_filenames(container_name: str, path: str) -> ContainerFileListResponse:
    """list files in a container volume path"""
    ret = await docker_list_directory(container_name, path)
    return ContainerFileListResponse(items=ret if ret else [])


@container.get(expand_api_url("{container_name}/fs"))
async def read_file(container_name: str, path: str):
    """read a file in a container volume, returns a tar archive of the file"""
    gen = docker_read_file(container_name=container_name, path=path)
    archive_size = await anext(gen)
    archive_size = int.from_bytes(archive_size, "big")
    if not archive_size:
        raise HTTPException(status_code=500, detail="failed to read file size")
    suggested_filename_base = os.path.basename(path)
    suggested_filename_no_ext, _ = os.path.splitext(suggested_filename_base)
    suggested_filename = f"{suggested_filename_no_ext}.tar"
    return StreamingResponse(
        gen,
        headers={
            "Content-Length": str(archive_size),
            "Content-Disposition": f'attachment; filename="{suggested_filename}"',
        },
        media_type="application/x-tar",
    )


def zip_handler(file: UploadFile, tar: tarfile.TarFile):
    in_file = zipfile.ZipFile(file.file)

    if not file.filename or not file.size:
        return ContainerFileUploadResponse(success=False)
    for item in in_file.filelist:
        info = tarfile.TarInfo(name=item.filename)
        info.size = item.file_size
        with in_file.open(item) as zip_item:
            tar.addfile(info, fileobj=zip_item)
    return


async def raw_handler(file: UploadFile, name: str, tar: tarfile.TarFile):
    info = tarfile.TarInfo(name=name or "download")
    info.size = file.size or 0
    tar.addfile(info, fileobj=file.file)


@container.post(expand_api_url("{container_name}/fs/upload/"), response_model=ContainerFileUploadResponse)
async def upload_file(
    container_name: str, path: Annotated[str, Form()], file: UploadFile
) -> ContainerFileUploadResponse:
    """upload a zip file to a container volume path, extracts zip and places contents in path"""
    ret = False
    await file.seek(0)
    tar_bytes = io.BytesIO()
    with tarfile.open(mode="w", fileobj=tar_bytes) as tmp_tar:
        if zipfile.is_zipfile(file.file):
            await file.seek(0)
            zip_handler(file, tmp_tar)
        else:
            await file.seek(0)
            await raw_handler(file, path.split("/")[-1], tmp_tar)

    tar_bytes.seek(0)
    ret = await docker_file_upload(container_name, path, tar_bytes.read())
    # raw file upload

    return ContainerFileUploadResponse(success=ret)


@container.post(expand_api_url("{container_name}/fs/delete/"), response_model=ContainerFileDeleteResponse)
async def delete_file(container_name: str, path: str):
    """delete a file in a container volume"""
    ret = await docker_delete_file(container_name, path)
    return ContainerFileDeleteResponse(success=ret)


@container.get(expand_api_url("{container_name}/command"), response_model=ContainerCommandResponse)
async def send_command(container_name: str, command: str):
    """send a command to a container"""
    ret = await docker_container_send_command(container_name, command)
    return ContainerCommandResponse(success=ret)


@container.get(expand_api_url("{container_name}/delete"), response_model=ContainerDeleteResponse)
async def delete_container(container_name: str):
    """delete a container by name"""
    ret = await docker_container_remove(container_name)
    return ContainerDeleteResponse(success=ret)
