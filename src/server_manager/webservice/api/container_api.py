import io
import tarfile
import zipfile

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from server_manager.webservice.docker_interface.docker_container_api import (
    docker_container_create,
    docker_container_get,
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
    ContainerCreateRequest,
    StringListResponse,
)
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.util import expand_api_url

container = APIRouter(tags=["container"])
metric_data_rate = 10


@container.get(expand_api_url("list"), response_model=StringListResponse)
async def list_containers():
    names = await docker_list_containers_names()
    return StringListResponse(values=names)


@container.get(expand_api_url("{name}"))
async def get_container(name: str):
    return await docker_container_get(name)


@container.get(expand_api_url("{name}/start"))
async def start_container(name: str):
    return await docker_container_start(name)


@container.get(expand_api_url("{name}/stop"))
async def stop_container(name: str):
    return await docker_container_stop(name)


@container.post(expand_api_url("create/{template_name}"))
async def create_container(container_create_req: ContainerCreateRequest):
    template = DB().get_template_by_name(container_create_req.template)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return await docker_container_create(
        container_create_req.server_name, template.image, container_create_req.port, container_create_req.env
    )


@container.get(expand_api_url("{container_name}/status"))
async def get_container_status(container_name: str):
    is_running = await docker_container_running(container_name)
    return {"running": is_running}


# @container.get(expand_api_url("{container_name}/metrics"))
# async def get_container_metrics(
#     container_name: str,
# ):
#     async def metrics_generator():
#         async for metrics in docker_container_metrics(container_name):
#             yield f"data: {metrics}\n\n"

#     return StreamingResponse(metrics_generator(), media_type="text/event-stream")


@container.get(expand_api_url("{container_name}/logs"))
async def get_log_message(container_name: str, line_count: int | None = None) -> list[str]:
    return await docker_container_logs_tail(container_name, tail=line_count or 25)


# Volume
@container.get(expand_api_url("{container_name}/fs/list"))
async def get_directory_filenames(container_name: str, path: str) -> list[str] | None:
    return await docker_list_directory(container_name, path)


@container.get(expand_api_url("{container_name}/fs"))
async def read_file(container_name: str, path: str):
    return StreamingResponse(docker_read_file(container_name, path), media_type="application/x-tar")


@container.post(expand_api_url("{container_name}/fs/upload/"))
async def upload_file(container_name: str, path: str, file: UploadFile):
    tar_bytes = io.BytesIO()
    zip_file = zipfile.ZipFile(file.file)
    with tarfile.open(mode="w", fileobj=tar_bytes) as tmp_tar:
        if not file.filename or not file.size:
            return False
        for item in zip_file.filelist:
            info = tarfile.TarInfo(name=item.filename)
            info.size = item.file_size
            with zip_file.open(item) as zip_item:
                tmp_tar.addfile(info, fileobj=zip_item)
    tar_bytes.seek(0)

    return await docker_file_upload(container_name, path, tar_bytes.read())


@container.post(expand_api_url("{container_name}/fs/delete/"))
async def delete_file(container_name: str, path: str):
    return await docker_delete_file(container_name, path)


@container.get(expand_api_url("{container_name}/command"))
async def send_command(container_name: str, command: str):
    return await docker_container_send_command(container_name, command)


@container.get(expand_api_url("{container_name}/delete"))
async def delete_container(container_name: str):
    return await docker_container_remove(container_name)
