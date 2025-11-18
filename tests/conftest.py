import multiprocessing
import os
from collections.abc import Generator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.mock_data import TEST_NODE_READ, TEST_TEMPLATE_READ, TEST_USER_READ


@pytest.fixture(scope="session")
def app_instance() -> Generator[FastAPI, Any, Any]:
    """
    Session-scoped fixture to initialize the FastAPI application once.
    Sets necessary environment variables before importing the app.
    """
    # Set environment variables needed for app initialization with purge_env_vars
    vars_to_purge = [
        "SM_SECRET_KEY",
        "SM_CADDY_FILE",
        "SM_SQL_SERVER_PATH",
        "SM_SQL_SERVER_PASSWORD",
        "SM_API_BACKEND",
        "SM_PORT_START",
        "SM_PORT_END",
        "SM_ENV",
        "SM_LOG_PATH",
        "SM_LOG_LEVEL",
        "SM_MOUNT_PATH",
    ]

    vars_to_save: dict[str, str] = {
        "SM_API_BACKEND": "localhost",
        "SM_LOG_LEVEL": "DEBUG",
        "SM_LOG_PATH": "./sm-log.log",
        "SM_MOUNT_PATH": "./sm-data",
    }
    monkeypatch = pytest.MonkeyPatch()
    original_env = {var: os.environ.get(var) for var in vars_to_purge}

    for var in vars_to_purge:
        monkeypatch.delenv(var, raising=False)
    for var, value in vars_to_save.items():
        monkeypatch.setenv(var, value)
    # Import the app after setting the environment
    from server_manager.webservice.webservice import app

    yield app
    for var, value in original_env.items():
        if value is not None:
            monkeypatch.setenv(var, value)
        else:
            monkeypatch.delenv(var, raising=False)

    monkeypatch.undo()


@pytest.fixture
def mock_db(mocker):
    lock = multiprocessing.Lock()

    def _mock_db():
        mock_db_instance = mocker.MagicMock()
        from server_manager.webservice.db_models import NodesRead, TemplatesRead, UsersRead

        # Configure default return values for common methods
        mock_db_instance.get_node.return_value = NodesRead(**TEST_NODE_READ)
        mock_db_instance.get_user.return_value = UsersRead(**TEST_USER_READ)
        mock_db_instance.get_template.return_value = TemplatesRead(**TEST_TEMPLATE_READ)

        return mock_db_instance

    with lock:
        yield _mock_db()


@pytest.fixture(scope="session")
def test_client(
    app_instance: FastAPI,
):
    """
    Session-scoped fixture to create a TestClient for the FastAPI application.
    """
    with TestClient(app_instance) as client:
        yield client


@pytest.fixture(scope="session")
def test_client_no_auth(app_instance: FastAPI):
    """
    Session-scoped fixture to create a TestClient for the FastAPI application.
    """
    from server_manager.webservice.db_models import UsersRead
    from server_manager.webservice.util.auth import auth_get_active_user

    print(os.environ)
    with TestClient(app_instance) as client:
        app_instance.dependency_overrides[auth_get_active_user] = lambda: UsersRead(**TEST_USER_READ)
        yield client
