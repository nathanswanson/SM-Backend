from types import SimpleNamespace

import pytest

from server_manager.webservice.db_models import ServersRead
from tests.mock_data import TEST_SERVER, TEST_SERVER_READ


@pytest.fixture(autouse=True)
def patch_db(mocker, mock_db):
    mocker.patch("server_manager.webservice.routes.server_api.DB", return_value=mock_db)
    mock_db.get_server_by_name.return_value = None
    return mock_db


def test_create_server_success(test_client_no_auth, mock_db, mocker):
    mock_db.get_template.return_value = SimpleNamespace(image="game", exposed_port=[3000])
    mock_db.get_server_by_name.return_value = None
    mock_db.unused_port.return_value = [4000]
    mock_db.create_server.return_value = ServersRead(**TEST_SERVER_READ)
    docker_create = mocker.patch(
        "server_manager.webservice.routes.server_api.docker_container_create",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )

    response = test_client_no_auth.post("/servers/", json=TEST_SERVER)

    assert response.status_code == 200
    assert response.json()["id"] == TEST_SERVER_READ["id"]
    docker_create.assert_awaited()
    mock_db.create_server.assert_called_once()


def test_create_server_duplicate_name_returns_400(test_client_no_auth, mock_db):
    mock_db.get_server_by_name.return_value = ServersRead(**TEST_SERVER_READ)

    response = test_client_no_auth.post("/servers/", json=TEST_SERVER)

    assert response.status_code == 400
    assert response.json()["detail"] == "Server with that name already exists"


def test_create_server_fails_when_docker_errors(test_client_no_auth, mock_db, mocker):
    mock_db.get_template.return_value = SimpleNamespace(image="game", exposed_port=[3000])
    mock_db.get_server_by_name.return_value = None
    mocker.patch(
        "server_manager.webservice.routes.server_api.docker_container_create",
        new_callable=mocker.AsyncMock,
        return_value=False,
    )

    response = test_client_no_auth.post("/servers/", json=TEST_SERVER)

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to create Docker container"


def test_create_server_returns_false_when_template_missing(test_client_no_auth, mock_db):
    mock_db.get_template.return_value = None
    mock_db.get_server_by_name.return_value = None

    response = test_client_no_auth.post("/servers/", json=TEST_SERVER)

    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found"


def test_delete_server_removes_container_and_record(test_client_no_auth, mock_db, mocker):
    mock_db.get_server.return_value = SimpleNamespace(container_name="mc", id=1)
    mock_db.delete_server.return_value = True
    docker_remove = mocker.patch(
        "server_manager.webservice.routes.server_api.docker_container_remove",
        new_callable=mocker.AsyncMock,
    )

    response = test_client_no_auth.delete("/servers/1")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    docker_remove.assert_awaited_once_with("mc")
    mock_db.delete_server.assert_called_once_with(1)


def test_delete_server_missing_returns_error(test_client_no_auth, mock_db):
    mock_db.get_server.return_value = None
    mock_db.delete_server.return_value = False

    response = test_client_no_auth.delete("/servers/1")

    assert response.status_code == 200
    assert response.json() == {"success": False}


def test_start_server_opens_ports(test_client_no_auth, mock_db, mocker):
    mock_db.get_server.return_value = SimpleNamespace(container_name="mc", id=1)
    mocker.patch(
        "server_manager.webservice.routes.server_api.docker_container_start",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )
    mock_router = mocker.patch("server_manager.webservice.routes.server_api.ServerRouter")
    mock_router_instance = mock_router.return_value
    mock_router_instance.open_ports = mocker.AsyncMock()

    response = test_client_no_auth.post("/servers/1/start")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    mock_router_instance.open_ports.assert_awaited_once()


def test_start_server_missing_returns_error(test_client_no_auth, mock_db):
    mock_db.get_server.return_value = None

    response = test_client_no_auth.post("/servers/1/start")

    assert response.status_code == 200
    assert response.json() == {"success": False}


def test_stop_server_closes_ports(test_client_no_auth, mock_db, mocker):
    mock_db.get_server.return_value = SimpleNamespace(container_name="mc", id=1)
    mocker.patch(
        "server_manager.webservice.routes.server_api.docker_container_stop",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )
    mock_router = mocker.patch(
        "server_manager.webservice.routes.server_api.ServerRouter",
        return_value=SimpleNamespace(close_ports=mocker.MagicMock(), open_ports=mocker.MagicMock()),
    )

    response = test_client_no_auth.post("/servers/1/stop")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    mock_router.return_value.close_ports.assert_called_once()


def test_stop_server_missing_returns_error(test_client_no_auth, mock_db):
    mock_db.get_server.return_value = None

    response = test_client_no_auth.post("/servers/1/stop")

    assert response.status_code == 200
    assert response.json() == {"success": False}


def test_get_server_status_running(test_client_no_auth, mock_db, mocker):
    mock_db.get_server.return_value = SimpleNamespace(container_name="mc", id=1)
    mocker.patch(
        "server_manager.webservice.routes.server_api.docker_container_running",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )
    mocker.patch(
        "server_manager.webservice.routes.server_api.docker_container_health_status",
        new_callable=mocker.AsyncMock,
        return_value="ok",
    )

    response = test_client_no_auth.get("/servers/1/status")

    assert response.status_code == 200
    assert response.json() == {"running": True, "health": "ok"}


def test_get_server_status_missing_server_returns_false(test_client_no_auth, mock_db):
    mock_db.get_server.return_value = None

    response = test_client_no_auth.get("/servers/1/status")

    assert response.status_code == 200
    assert response.json() == {"running": False, "health": None}


def test_send_command_missing_server_returns_404(test_client_no_auth, mock_db):
    mock_db.get_server.return_value = None

    response = test_client_no_auth.post("/servers/1/command", params={"command": "say hi"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


def test_send_command_invokes_docker_command(test_client_no_auth, mock_db, mocker):
    mock_db.get_server.return_value = SimpleNamespace(container_name="mc", id=1)
    mocker.patch(
        "server_manager.webservice.routes.server_api.docker_container_send_command",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )

    response = test_client_no_auth.post("/servers/1/command", params={"command": "say hi"})

    assert response.status_code == 200
    assert response.json() == {"success": True}
