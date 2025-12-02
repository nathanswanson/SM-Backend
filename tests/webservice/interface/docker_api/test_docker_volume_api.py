import io
import tarfile
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from server_manager.webservice.interface.docker_api.docker_volume_api import (
    DockerError,
    docker_delete_file,
    docker_file_upload,
    docker_list_directory,
    docker_read_file,
    docker_read_tarfile,
    docker_volume_path,
)


def _patch_container_ctx(mocker, container):
    @asynccontextmanager
    async def _ctx(_name):
        yield container

    mocker.patch("server_manager.webservice.interface.docker.docker_volume_api.docker_container", _ctx)


class _DummyExec:
    def __init__(self, payload: bytes):
        self.payload = payload

    def start(self):
        """Mirror docker exec object where start returns stream synchronously."""
        return _DummyStream(self.payload)


class _DummyStream:
    def __init__(self, payload: bytes):
        self.payload = payload

    async def read_out(self):
        return SimpleNamespace(data=self.payload)


@pytest.mark.asyncio
async def test_docker_list_directory_returns_file_and_dir_lists(mocker):
    file_exec = _DummyExec(b"config/settings.cfg\nlogs/output.log\n")
    dir_exec = _DummyExec(b".\nconfig\n")
    container = SimpleNamespace(exec=mocker.AsyncMock(side_effect=[file_exec, dir_exec]))
    _patch_container_ctx(mocker, container)

    list_dir = await docker_list_directory("server", "/base")
    assert list_dir is not None
    files, dirs = list_dir

    assert files == ["config/settings.cfg", "logs/output.log"]
    assert dirs == [".", "config"]
    assert container.exec.await_args_list[0].args[0][:2] == ["find", "/base"]


@pytest.mark.asyncio
async def test_docker_list_directory_returns_none_when_no_container(mocker):
    _patch_container_ctx(mocker, None)

    assert await docker_list_directory("ghost", "/") is None


@pytest.mark.asyncio
async def test_docker_read_file_yields_size_and_chunks(mocker):
    file_bytes = b"abc123"
    tarinfo = tarfile.TarInfo(name="file.txt")
    tarinfo.size = len(file_bytes)
    tarinfo.offset_data = 0

    class _DummyArchive:
        def __init__(self):
            self.fileobj = io.BytesIO(file_bytes)

        def getmembers(self):
            return [tarinfo]

    container = SimpleNamespace(get_archive=mocker.AsyncMock(return_value=_DummyArchive()))
    _patch_container_ctx(mocker, container)

    chunks = [chunk async for chunk in docker_read_file("server", "/file.txt")]

    assert chunks[0] == len(file_bytes).to_bytes(8, "big")
    assert b"".join(chunks[1:]) == file_bytes


@pytest.mark.asyncio
async def test_docker_read_file_missing_returns_negative_one(mocker):
    class _EmptyArchive:
        fileobj = None

        @staticmethod
        def getmembers():
            return []

    container = SimpleNamespace(get_archive=mocker.AsyncMock(return_value=_EmptyArchive()))
    _patch_container_ctx(mocker, container)

    chunks = [chunk async for chunk in docker_read_file("server", "/missing.txt")]

    assert chunks == [-1]


@pytest.mark.asyncio
async def test_docker_read_tarfile_passes_through_archive(mocker):
    archive = object()
    container = SimpleNamespace(get_archive=mocker.AsyncMock(return_value=archive))
    _patch_container_ctx(mocker, container)

    result = await docker_read_tarfile("server", "/archive.tar")

    assert result is archive
    container.get_archive.assert_awaited_once_with("/archive.tar")


@pytest.mark.asyncio
async def test_docker_file_upload_puts_archive_and_returns_true(mocker):
    container = SimpleNamespace(put_archive=mocker.AsyncMock(return_value=None))
    _patch_container_ctx(mocker, container)

    result = await docker_file_upload("server", "/path/to/file.txt", b"tar-bytes")

    assert result is True
    container.put_archive.assert_awaited_once_with("/path/to", b"tar-bytes")


@pytest.mark.asyncio
async def test_docker_file_upload_handles_docker_error(mocker):
    container = SimpleNamespace(put_archive=mocker.AsyncMock(side_effect=DockerError(500, {"message": "boom"})))
    _patch_container_ctx(mocker, container)

    result = await docker_file_upload("server", "/path/file.txt", b"tar")

    assert result is False


@pytest.mark.asyncio
async def test_docker_file_upload_returns_false_without_container(mocker):
    _patch_container_ctx(mocker, None)

    assert await docker_file_upload("server", "/path/file.txt", b"tar") is False


@pytest.mark.asyncio
async def test_docker_delete_file_executes_command(mocker):
    container = SimpleNamespace(exec=mocker.AsyncMock(return_value=None))
    _patch_container_ctx(mocker, container)

    result = await docker_delete_file("server", "/tmp/file.txt")

    assert result is True
    container.exec.assert_awaited_once_with("rm -rf /tmp/file.txt")


def test_docker_volume_path_constructs_host_path(monkeypatch):
    monkeypatch.setenv("SM_MOUNT_PATH", "/mnt/server")

    full_path = docker_volume_path("container", "/cfg/settings.conf")

    assert full_path == "/mnt/server/container/cfg/settings.conf"
