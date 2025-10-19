# Volume
import io
import os
import tarfile
import zipfile

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from server_manager.webservice.docker_interface.docker_volume_api import (
    docker_delete_file,
    docker_file_upload,
    docker_read_file,
)
from server_manager.webservice.models import (
    ContainerFileDeleteResponse,
    ContainerFileUploadResponse,
)

router = APIRouter()


@router.get("/{container_name}/fs")
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


@router.post("/{container_name}/fs/{path}", response_model=ContainerFileUploadResponse)
async def upload_file(container_name: str, path: str, file: UploadFile) -> ContainerFileUploadResponse:
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


@router.delete("/{container_name}/fs/{path}", response_model=ContainerFileDeleteResponse)
async def delete_file(container_name: str, path: str):
    """delete a file in a container volume"""
    ret = await docker_delete_file(container_name, path)
    return ContainerFileDeleteResponse(success=ret)
