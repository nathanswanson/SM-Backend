"""
container_api.py

API endpoints for managing Docker containers and their associated volumes.

Author: Nathan Swanson

"""

import io
import tarfile
import zipfile

from fastapi import APIRouter, HTTPException
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
    ContainerFileUploadRequest,
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
    return StreamingResponse(docker_read_file(container_name, path), media_type="application/x-tar")


@container.post(expand_api_url("{container_name}/fs/upload/"), response_model=ContainerFileUploadResponse)
async def upload_file(
    container_name: str, container_file_upload_req: ContainerFileUploadRequest
) -> ContainerFileUploadResponse:
    """upload a zip file to a container volume path, extracts zip and places contents in path"""
    tar_bytes = io.BytesIO()
    zip_file = zipfile.ZipFile(container_file_upload_req.file.file)
    with tarfile.open(mode="w", fileobj=tar_bytes) as tmp_tar:
        if not container_file_upload_req.file.filename or not container_file_upload_req.file.size:
            return ContainerFileUploadResponse(success=False)
        for item in zip_file.filelist:
            info = tarfile.TarInfo(name=item.filename)
            info.size = item.file_size
            with zip_file.open(item) as zip_item:
                tmp_tar.addfile(info, fileobj=zip_item)
    tar_bytes.seek(0)
    ret = await docker_file_upload(container_name, container_file_upload_req.path, tar_bytes.read())
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
