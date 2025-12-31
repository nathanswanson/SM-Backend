from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
import requests
from pytest_mock import MockerFixture

from server_manager.webservice.db_models import ServersRead, TemplatesRead
from server_manager.webservice.interface.docker_api.server_router import ServerRouter
from tests.mock_data import TEST_SERVER_READ, TEST_TEMPLATE_READ


@pytest.fixture
def mock_post(mocker: MockerFixture) -> MagicMock:
    """Fixture to mock requests.post."""
    return mocker.patch("requests.post")


@pytest.fixture
def mock_delete(mocker: MockerFixture) -> MagicMock:
    """Fixture to mock requests.delete."""
    return mocker.patch("requests.delete")


@pytest.fixture
def mock_server_router(mocker: MockerFixture, mock_db) -> ServerRouter:
    """
    Provides a ServerRouter instance with mocked dependencies.
    Returns a dictionary containing the router instance and its mocks.
    """
    # Prevent the original __init__ from running with its side effects
    mocker.patch("server_manager.webservice.net.server_router.ServerRouter.__init__", return_value=None)
    mocker.patch("server_manager.webservice.routes.template_api.get_db", return_value=mock_db)
    mocker.patch("server_manager.webservice.net.server_router.DB", return_value=mock_db)
    mock_template = mocker.MagicMock()
    mock_template.exposed_port = [25565]
    mock_db.get_template.return_value = mock_template

    # mock_post = mocker.patch("requests.post")

    return ServerRouter()


def test_add_caddy_route_success(mock_server_router: ServerRouter, mock_post: MagicMock):
    """Test that add_caddy_route returns True on success."""

    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"status": "ok"}
    mock_post.return_value = mock_response

    result = mock_server_router.add_caddy_route("test_container", {8080: 30000})
    assert result is True
    mock_post.assert_called_once()


def test_add_caddy_route_failure(mock_server_router: ServerRouter, mock_post: MagicMock):
    """Test that add_caddy_route returns False on non-OK status."""

    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.BAD_REQUEST
    mock_post.return_value = mock_response

    result = mock_server_router.add_caddy_route("test_container", {8080: 30000})
    assert result is False


def test_add_caddy_route_exception(mock_server_router: ServerRouter, mock_post: MagicMock):
    """Test that add_caddy_route returns False when requests raises an exception."""
    mock_post.side_effect = requests.RequestException("Caddy down")
    result = mock_server_router.add_caddy_route("test_container", {8080: 30000})
    assert result is False


@pytest.mark.asyncio
async def test_open_ports(mocker: MockerFixture, mock_server_router: ServerRouter, mock_db):
    """
    Tests that open_ports successfully calls add_caddy_route
    when a valid server and template are provided.
    """
    # Arrange

    mock_container_exists = mocker.patch(
        "server_manager.webservice.net.server_router.docker_container_name_exists",
        new_callable=mocker.AsyncMock,
    )
    mock_container_exists.return_value = True
    mock_add_caddy_route = mocker.patch.object(ServerRouter, "add_caddy_route", return_value=True)

    server = ServersRead(**TEST_SERVER_READ)

    # Act
    result = await mock_server_router.open_ports(server)

    # Assert
    assert result is True
    mock_db.get_template.assert_called_once_with(server.template_id)
    mock_add_caddy_route.assert_called_once_with(server.container_name, {25565: 30001})


@pytest.mark.asyncio
async def test_open_ports_container_not_exists(mocker: MockerFixture, mock_server_router: ServerRouter):
    """Test open_ports when the container does not exist."""
    mock_container_exists = mocker.patch(
        "server_manager.webservice.net.server_router.docker_container_name_exists", new_callable=mocker.AsyncMock
    )
    mock_container_exists.return_value = False
    server = ServersRead(**TEST_SERVER_READ)
    result = await mock_server_router.open_ports(server)
    assert result is False


@pytest.mark.asyncio
async def test_open_ports_mismatched_ports(mocker: MockerFixture, mock_server_router: ServerRouter, mock_db):
    """Test open_ports when the number of exposed ports and mapped ports do not match."""
    # Arrange
    mocker.patch(
        "server_manager.webservice.net.server_router.docker_container_name_exists",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )

    # Reconfigure mock_db.get_template to return a template with 2 exposed ports
    mock_template = TemplatesRead(**TEST_TEMPLATE_READ)
    mock_template.exposed_port = [25565, 25566]  # Two exposed ports
    mock_db.get_template.return_value = mock_template

    server = ServersRead(**TEST_SERVER_READ)

    # Act
    result = await mock_server_router.open_ports(server)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_open_ports_none_server(mock_server_router: ServerRouter) -> None:
    """Test that open_ports returns False when the server is None."""
    result = await mock_server_router.open_ports(None)
    assert result is False


def test_server_router_init(mocker: MockerFixture):
    """Test that the ServerRouter __init__ calls requests.post."""
    mock_post = mocker.patch("requests.post")
    # Reset singleton for this test to ensure __init__ is called
    ServerRouter._instances = {}
    ServerRouter()
    mock_post.assert_called_once_with("http://rproxy:2019/config/apps/layer4/servers", json={}, timeout=5)


def test_close_ports_success(mocker: MockerFixture, mock_server_router: ServerRouter):
    """Test that close_ports returns True on success."""

    mock_delete = mocker.patch("requests.delete")
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_delete.return_value = mock_response

    server = ServersRead(**TEST_SERVER_READ)
    result = mock_server_router.close_ports(server)

    assert result is True
    mock_delete.assert_called_once_with(f"http://rproxy:2019/id/{server.container_name}", timeout=5)


def test_close_ports_failure(mocker: MockerFixture, mock_server_router: ServerRouter):
    """Test that close_ports returns False on non-OK status."""
    mock_delete = mocker.patch("requests.delete")
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.BAD_REQUEST
    mock_delete.return_value = mock_response

    server = ServersRead(**TEST_SERVER_READ)
    result = mock_server_router.close_ports(server)

    assert result is False


def test_close_ports_exception(mocker: MockerFixture, mock_server_router: ServerRouter):
    """Test that close_ports returns False when requests raises an exception."""
    mocker.patch("requests.delete", side_effect=requests.RequestException("Caddy down"))
    server = ServersRead(**TEST_SERVER_READ)
    result = mock_server_router.close_ports(server)
    assert result is False
