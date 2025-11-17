import multiprocessing
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server_manager.webservice.db_models import (
    NodesRead,
    TemplatesRead,
    UsersRead,
)
from server_manager.webservice.util.auth import auth_get_active_user
from tests.mock_data import TEST_NODE_READ, TEST_TEMPLATE_READ, TEST_USER_READ


@pytest.fixture(scope="session")
def app_instance() -> FastAPI:
    """
    Session-scoped fixture to initialize the FastAPI application once.
    Sets necessary environment variables before importing the app.
    """
    # Set environment variables needed for app initialization
    os.environ["SM_MOUNT_PATH"] = "/tmp/server_manager_test_mount"
    os.environ["SM_API_BACKEND"] = "localhost"

    # Import the app after setting the environment
    from server_manager.webservice.webservice import app

    return app


@pytest.fixture
def mock_db(mocker):
    lock = multiprocessing.Lock()

    def _mock_db():
        mock_db_instance = mocker.MagicMock()

        # Configure default return values for common methods
        mock_db_instance.get_node.return_value = NodesRead(**TEST_NODE_READ)
        mock_db_instance.get_user.return_value = UsersRead(**TEST_USER_READ)
        mock_db_instance.get_template.return_value = TemplatesRead(**TEST_TEMPLATE_READ)

        return mock_db_instance

    with lock:
        yield _mock_db()


@pytest.fixture(scope="session")
def test_client(app_instance: FastAPI):
    """
    Session-scoped fixture to create a TestClient for the FastAPI application.
    """
    with TestClient(app_instance) as client:
        yield client


def override_no_auth():
    return UsersRead(**TEST_USER_READ)


@pytest.fixture(scope="session")
def test_client_no_auth(app_instance: FastAPI):
    """
    Session-scoped fixture to create a TestClient for the FastAPI application.
    """
    with TestClient(app_instance) as client:
        app_instance.dependency_overrides[auth_get_active_user] = override_no_auth
        yield client
