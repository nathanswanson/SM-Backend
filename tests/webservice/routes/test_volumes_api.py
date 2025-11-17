import io
import tarfile
from types import SimpleNamespace

import pytest


def async_bytes_stream(payload: bytes):
    async def generator():
        yield len(payload).to_bytes(8, "big")
        yield payload

    return generator()


def async_zero_stream():
    async def generator():
        yield (0).to_bytes(8, "big")

    return generator()


class DummyTar:
    def __init__(self, file_bytes: bytes):
        self._file_bytes = file_bytes
        info = tarfile.TarInfo(name="file.txt")
        info.size = len(file_bytes)
        self._member = info

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getmembers(self):
        return [self._member]

    def extractfile(self, _member):
        return io.BytesIO(self._file_bytes)


@pytest.fixture(autouse=True)
def patch_db(mocker, mock_db):
    mocker.patch("server_manager.webservice.routes.volumes_api.DB", return_value=mock_db)
    return mock_db


def test_get_archive_streams_filtered_paths(test_client_no_auth, mock_db, mocker):
    mock_db.get_server.return_value = SimpleNamespace(template_id=3, container_name="mc")
    mock_db.get_template.return_value = SimpleNamespace(exposed_volume=["/world", "/config"])
    mocker.patch(
        "server_manager.webservice.routes.volumes_api.docker_read_tarfile",
        new_callable=mocker.AsyncMock,
        return_value=DummyTar(b"data"),
    )

    response = test_client_no_auth.get("/volumes/1/fs/archive", params={"paths": str(["/world", "/secret"])})

    assert response.status_code == 200
    assert int(response.headers["Content-Length"]) == len(response.content)


def test_get_archive_missing_server_returns_404(test_client_no_auth, mock_db):
    mock_db.get_server.return_value = None

    response = test_client_no_auth.get("/volumes/99/fs/archive")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


def test_get_archive_without_exposed_volume_returns_400(test_client_no_auth, mock_db):
    mock_db.get_server.return_value = SimpleNamespace(template_id=3)
    mock_db.get_template.return_value = SimpleNamespace(exposed_volume=None)

    response = test_client_no_auth.get("/volumes/1/fs/archive")

    assert response.status_code == 400
    assert response.json()["detail"] == "No exposed volumes for this server"


def test_read_file_returns_tar_stream(test_client_no_auth, mock_db, mocker):
    mock_db.get_server.return_value = SimpleNamespace(container_name="mc")
    payload = b"tar-bytes"
    mocker.patch(
        "server_manager.webservice.routes.volumes_api.docker_read_file",
        return_value=async_bytes_stream(payload),
    )

    response = test_client_no_auth.get("/volumes/1/fs", params={"path": "/data/config"})

    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["Content-Length"] == str(len(payload))


def test_read_file_zero_size_returns_500(test_client_no_auth, mock_db, mocker):
    mock_db.get_server.return_value = SimpleNamespace(container_name="mc")
    mocker.patch(
        "server_manager.webservice.routes.volumes_api.docker_read_file",
        return_value=async_zero_stream(),
    )

    response = test_client_no_auth.get("/volumes/1/fs", params={"path": "/data/config"})

    assert response.status_code == 500
    assert response.json()["detail"] == "failed to read file size"


def test_upload_file_pushes_tar_to_docker(test_client_no_auth, mock_db, mocker):
    mock_db.get_server.return_value = SimpleNamespace(container_name="mc")
    docker_upload = mocker.patch(
        "server_manager.webservice.routes.volumes_api.docker_file_upload",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )

    response = test_client_no_auth.post(
        "/volumes/1/fs/",
        params={"path": "/data/file.txt"},
        data=b"payload",
        headers={"Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    docker_upload.assert_awaited_once()


def test_upload_file_missing_server_returns_404(test_client_no_auth, mock_db):
    mock_db.get_server.return_value = None

    response = test_client_no_auth.post(
        "/volumes/1/fs/",
        params={"path": "/data/file.txt"},
        data=b"payload",
        headers={"Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


def test_delete_file_calls_docker(test_client_no_auth, mocker):
    mocker.patch(
        "server_manager.webservice.routes.volumes_api.docker_delete_file",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )

    response = test_client_no_auth.delete("/volumes/1/fs/some", params={"container_name": "mc", "path": "/some"})

    assert response.status_code == 200
    assert response.json() == {"success": True}
