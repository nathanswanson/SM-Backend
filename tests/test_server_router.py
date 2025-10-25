import os
from typing import cast
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server_manager.webservice.db_models import Servers, Templates, Users
from server_manager.webservice.net import server_router
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.data_access import DB

os.environ["SM_ENV"] = "TEST"
# Use an in-memory SQLite database for tests for simplicity.
# For tests involving postgres-specific features, you'd point this to a test Postgres DB.
os.environ["SM_DB_CONNECTION"] = "sqlite:///:memory:"
os.environ["SM_STATIC_PATH"] = "/tmp"  # Dummy path for tests
os.environ["SM_API_BACKEND"] = "localhost"
# The app from webservice is the socketio app, we need the underlying fastapi app
from server_manager.webservice.webservice import fastapi_app as fastapi_app

app: FastAPI = cast(FastAPI, fastapi_app.other_asgi_app)
client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_auth():
    """Mock the authentication dependency."""
    app.dependency_overrides[auth_get_active_user] = lambda: Users(
        id=1, username="testuser", admin=True, hashed_password="password", disabled=False
    )
    yield
    app.dependency_overrides = {}


@pytest.fixture
def mock_db():
    """Mock the database access."""
    with patch.object(server_router, "DB", spec=DB) as mock_db_class:
        mock_db_instance = mock_db_class.return_value
        yield mock_db_instance


@pytest.fixture
def mock_docker():
    """Mock the docker functions."""
    with (
        patch.object(server_router, "docker_container_create") as mock_create,
        patch.object(server_router, "docker_container_remove") as mock_remove,
        patch.object(server_router, "docker_container_start") as mock_start,
        patch.object(server_router, "docker_container_stop") as mock_stop,
    ):
        yield {"create": mock_create, "remove": mock_remove, "start": mock_start, "stop": mock_stop}


def test_get_servers(mock_db):
    """Test the get_servers endpoint."""
    mock_db.get_servers.return_value = [
        Servers(
            id=1,
            name="server1",
            container_name="c_server1",
            template_id=1,
            node_id=1,
            cpu=1,
            memory=1024,
            disk=10,
            port=[],
            env={},
        ),
        Servers(
            id=2,
            name="server2",
            container_name="c_server2",
            template_id=1,
            node_id=1,
            cpu=1,
            memory=1024,
            disk=10,
            port=[],
            env={},
        ),
    ]
    response = client.get("/server")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["name"] == "server1"
    mock_db.get_servers.assert_called_once()


def test_get_server(mock_db):
    """Test the get_server endpoint."""
    mock_db.get_server.return_value = Servers(
        id=1,
        name="server1",
        container_name="c_server1",
        template_id=1,
        node_id=1,
        cpu=1,
        memory=1024,
        disk=10,
        port=[],
        env={},
    )
    response = client.get("/server/1")
    assert response.status_code == 200
    assert response.json()["name"] == "server1"
    mock_db.get_server.assert_called_with(1)


def test_get_server_not_found(mock_db):
    """Test the get_server endpoint when server is not found."""
    mock_db.get_server.return_value = None
    response = client.get("/server/999")
    assert response.status_code == 404
    mock_db.get_server.assert_called_with(999)


def test_create_server(mock_db, mock_docker):
    """Test the create_server endpoint."""
    server_data = {"name": "new-server", "template_id": 1, "node_id": 1, "cpu": 2, "memory": 2048, "disk": 20}
    mock_db.get_template.return_value = Templates(
        id=1,
        name="template1",
        image="test-image",
        exposed_port=[8080],
        tags=[],
        resource_min_cpu=0,
        resource_min_disk=0,
        resource_min_mem=0,
        modules=[],
    )
    mock_db.create_server.return_value = Servers(id=3, container_name="c_new-server", port=[], env={}, **server_data)
    mock_docker["create"].return_value = True

    response = client.post("/server", json=server_data)

    assert response.status_code == 200
    assert response.json()["name"] == "new-server"
    mock_db.create_server.assert_called_once()
    mock_docker["create"].assert_called_once()


def test_create_server_template_not_found(mock_db):
    """Test create_server with a non-existent template."""
    server_data = {"name": "new-server", "template_id": 999, "node_id": 1, "cpu": 1, "memory": 1024, "disk": 10}
    mock_db.get_template.return_value = None
    response = client.post("/server", json=server_data)
    assert response.status_code == 404
    assert "Template not found" in response.json()["detail"]
    mock_db.get_template.assert_called_with(999)


def test_delete_server(mock_db, mock_docker):
    """Test the delete_server endpoint."""
    mock_db.get_server.return_value = Servers(
        id=1,
        name="server1",
        container_name="c_server1",
        template_id=1,
        node_id=1,
        cpu=1,
        memory=1024,
        disk=10,
        port=[],
        env={},
    )
    mock_docker["remove"].return_value = True
    mock_db.delete_server.return_value = True

    response = client.delete("/server/1")
    assert response.status_code == 200
    assert response.json()["message"] == "Server server1 deleted"
    mock_db.delete_server.assert_called_with(1)
    mock_docker["remove"].assert_called_with("c_server1")


def test_delete_server_not_found(mock_db):
    """Test deleting a server that does not exist."""
    mock_db.get_server.return_value = None
    response = client.delete("/server/999")
    assert response.status_code == 404
    assert "Server not found" in response.json()["detail"]


def test_start_server(mock_db, mock_docker):
    """Test the start_server endpoint."""
    mock_db.get_server.return_value = Servers(
        id=1,
        name="server1",
        container_name="c_server1",
        template_id=1,
        node_id=1,
        cpu=1,
        memory=1024,
        disk=10,
        port=[],
        env={},
    )
    mock_docker["start"].return_value = True

    response = client.post("/server/1/start")
    assert response.status_code == 200
    assert response.json()["message"] == "Server server1 started"
    mock_docker["start"].assert_called_with("c_server1")


def test_start_server_not_found(mock_db, mock_docker):
    """Test starting a server that does not exist."""
    mock_db.get_server.return_value = None
    response = client.post("/server/999/start")
    assert response.status_code == 404
    mock_docker["start"].assert_not_called()


def test_stop_server(mock_db, mock_docker):
    """Test the stop_server endpoint."""
    mock_db.get_server.return_value = Servers(
        id=1,
        name="server1",
        container_name="c_server1",
        template_id=1,
        node_id=1,
        cpu=1,
        memory=1024,
        disk=10,
        port=[],
        env={},
    )
    mock_docker["stop"].return_value = True

    response = client.post("/server/1/stop")
    assert response.status_code == 200
    assert response.json()["message"] == "Server server1 stopped"
    mock_docker["stop"].assert_called_with("c_server1")


def test_stop_server_not_found(mock_db, mock_docker):
    """Test stopping a server that does not exist."""
    mock_db.get_server.return_value = None
    response = client.post("/server/999/stop")
    assert response.status_code == 404
    mock_docker["stop"].assert_not_called()
