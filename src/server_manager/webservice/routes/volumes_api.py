# Volume

from fastapi import APIRouter

router = APIRouter()


# @router.get("/{server_id}/fs/archive")
# async def get_archive(server_id: int, paths: str | None = None):
#     actual_paths = ast.literal_eval(paths) if paths else None
#     server = DB().get_server(server_id)
#     if not server:
#         raise HTTPException(status_code=404, detail="Server not found")
#     exposed_volume = DB().get_template(server.template_id).exposed_volume  # type: ignore
#     if not exposed_volume:
#         raise HTTPException(status_code=400, detail="No exposed volumes for this server")
#     exposed_volume = set(exposed_volume)
#     if actual_paths is None:
#         actual_paths = exposed_volume if exposed_volume else set()

#     elif isinstance(actual_paths, str):
#         actual_paths = {actual_paths}
#     else:
#         actual_paths = set(actual_paths)

#     if not actual_paths:
#         raise HTTPException(status_code=400, detail="No valid paths provided")
#     actual_paths = actual_paths.intersection(set(exposed_volume))
#     tar_bytes = io.BytesIO()
#     with tarfile.open(fileobj=tar_bytes, mode="w|gz") as tar_file:
#         for path in actual_paths:
#             with await docker_read_tarfile(container_name=server.container_name, path=path) as docker_reader:
#                 for member in docker_reader.getmembers():
#                     file_obj = docker_reader.extractfile(member)
#                     if file_obj:
#                         tar_file.addfile(member, fileobj=file_obj)
#     tar_bytes.seek(0)

#     return StreamingResponse(
#         tar_bytes, media_type="application/x-tar", headers={"Content-Length": str(len(tar_bytes.getvalue()))}
#     )


# @router.get("/{server_id}/fs")
# async def read_file(server_id: int, path: str):
#     """read a file in a container volume, returns a tar archive of the file"""
#     server = DB().get_server(server_id)  # verify server exists
#     if not server:
#         raise HTTPException(status_code=404, detail="Server not found")

#     gen = docker_read_file(container_name=server.container_name, path=path)
#     archive_size = await anext(gen)
#     archive_size = int.from_bytes(archive_size, "big")
#     if not archive_size:
#         raise HTTPException(status_code=500, detail="failed to read file size")
#     suggested_filename_base = os.path.basename(path)
#     suggested_filename_no_ext, _ = os.path.splitext(suggested_filename_base)
#     suggested_filename = f"{suggested_filename_no_ext}.tar"
#     return StreamingResponse(
#         gen,
#         headers={
#             "Content-Length": str(archive_size),
#             "Content-Disposition": f'attachment; filename="{suggested_filename}"',
#         },
#         media_type="application/x-tar",
#     )


# def zip_handler(file: UploadFile, tar: tarfile.TarFile):
#     in_file = zipfile.ZipFile(file.file)

#     if not file.filename or not file.size:
#         return ContainerFileUploadResponse(success=False)
#     for item in in_file.filelist:
#         info = tarfile.TarInfo(name=item.filename)
#         info.size = item.file_size
#         with in_file.open(item) as zip_item:
#             tar.addfile(info, fileobj=zip_item)
#     return


# async def raw_handler(file: UploadFile, name: str, tar: tarfile.TarFile):
#     info = tarfile.TarInfo(name=name or "download")
#     info.size = file.size or 0
#     tar.addfile(info, fileobj=file.file)


# @router.post("/{server_id}/fs/", response_model=ContainerFileUploadResponse)
# async def upload_file(request: Request, server_id: int, path: Annotated[str, Query()]) -> ContainerFileUploadResponse:
#     """upload a zip file to a container volume path, extracts zip and places contents in path"""
#     server = DB().get_server(server_id)  # verify server exists
#     if not server:
#         raise HTTPException(status_code=404, detail="Server not found")
#     data = bytearray()
#     # currently this requires the entire file to be read into memory
#     async for chunk in request.stream():
#         data.extend(chunk)
#     tar_bytes = io.BytesIO()
#     with tarfile.open(mode="w", fileobj=tar_bytes) as tmp_tar:
#         tar_info = tarfile.TarInfo(name=os.path.basename(path))
#         tar_info.size = len(data)
#         tmp_tar.addfile(tar_info, io.BytesIO(data))
#     ret = await docker_file_upload(
#         container_name=server.container_name, path=os.path.dirname(path), data=tar_bytes.getvalue()
#     )
#     tar_bytes.close()
#     return ContainerFileUploadResponse(success=ret)


# @router.delete("/{server_id}/fs/{path}", response_model=ContainerFileDeleteResponse)
# async def delete_file(container_name: str, path: str):
#     """delete a file in a container volume"""
#     ret = await docker_delete_file(container_name, path)
#     return ContainerFileDeleteResponse(success=ret)
