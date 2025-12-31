# Volume

import ast
import io
import os
import tarfile
import zipfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from server_manager.webservice.interface.interface import ControllerVolumeInterface
from server_manager.webservice.interface.interface_manager import get_volume_client
from server_manager.webservice.models import ContainerFileDeleteResponse, ContainerFileUploadResponse
from server_manager.webservice.util.data_access import DB, get_db

router = APIRouter()


def _normalize_path(path: str) -> str:
    # path must not have leading slash, no .. components, and use / as separator, no double slashes
    parts = []
    for part in path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


@router.get("/{server_id}/fs/archive")
async def get_archive(
    server_id: int,
    client: Annotated[ControllerVolumeInterface, Depends(get_volume_client)],
    db: Annotated[DB, Depends(get_db)],
    paths: str | None = None,
):
    paths = "/" + paths.lstrip("/")
    actual_paths = ast.literal_eval(paths) if paths else None
    server = db.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    exposed_volume = db.get_template(server.template_id).exposed_volume  # type: ignore
    if not exposed_volume:
        raise HTTPException(status_code=400, detail="No exposed volumes for this server")
    exposed_volume = set(exposed_volume)
    if actual_paths is None:
        actual_paths = exposed_volume if exposed_volume else set()

    elif isinstance(actual_paths, str):
        actual_paths = {actual_paths}
    else:
        actual_paths = set(actual_paths)

    if not actual_paths:
        raise HTTPException(status_code=400, detail="No valid paths provided")
    actual_paths = actual_paths.intersection(set(exposed_volume))
    tar_bytes = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes, mode="w|gz") as tar_file:
        for path in actual_paths:
            with await client.read_archive(
                deployment_name=server.container_name, namespace=f"tenant-{server.linked_users[0].id}", path=path
            ) as reader:
                for member in reader.getmembers():
                    file_obj = reader.extractfile(member)
                    if file_obj:
                        tar_file.addfile(member, fileobj=file_obj)
    tar_bytes.seek(0)

    return StreamingResponse(
        tar_bytes, media_type="application/x-tar", headers={"Content-Length": str(len(tar_bytes.getvalue()))}
    )


@router.get("/{server_id}/fs")
async def read_file(
    server_id: int,
    path: Annotated[str, Query(description="Absolute path to file")],  # Already uses query
    client: Annotated[ControllerVolumeInterface, Depends(get_volume_client)],
    db: Annotated[DB, Depends(get_db)],
):
    """read a file in a container volume, returns a tar archive of the file"""
    server = db.get_server(server_id)  # verify server exists
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    path = "/" + path.lstrip("/")

    gen = await client.read_file(
        deployment_name=server.container_name,
        namespace=f"tenant-{server.linked_users[0].id}",
        path=path,
        username=server.linked_users[0].username,
    )

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


@router.post(
    "/{server_id}/fs/",
    openapi_extra={
        "requestBody": {
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
            "required": True,
        }
    },
    response_model=ContainerFileUploadResponse,
)
async def upload_file(
    request: Request,
    server_id: int,
    path: Annotated[str, Query()],
    client: Annotated[ControllerVolumeInterface, Depends(get_volume_client)],
    db: Annotated[DB, Depends(get_db)],
) -> ContainerFileUploadResponse:
    """upload a file to a container volume path"""
    path = "/" + path.lstrip("/")
    server = db.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)

    ret = await client.write_file(
        deployment_name=server.container_name,
        path=path,
        data=bytes(data),
        namespace=f"tenant-{server.linked_users[0].id}",
        username=server.linked_users[0].username,
    )
    return ContainerFileUploadResponse(success=ret)


@router.delete("/{server_id}/fs")  # Change from path param
async def delete_file(
    server_id: int,
    path: Annotated[str, Query(description="Absolute path to file")],
    client: Annotated[ControllerVolumeInterface, Depends(get_volume_client)],
    db: Annotated[DB, Depends(get_db)],
) -> ContainerFileDeleteResponse:
    """delete a file in a container volume"""
    server = db.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    ret = await client.delete_file(
        server.container_name, f"tenant-{server.linked_users[0].id}", path, server.linked_users[0].username
    )
    return ContainerFileDeleteResponse(success=ret)
