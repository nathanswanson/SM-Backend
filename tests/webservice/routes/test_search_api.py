from contextlib import contextmanager
from types import SimpleNamespace

from server_manager.webservice.db_models import Users
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.data_access import get_db


@contextmanager
def override_dependency(app, dependency, provider):
    """Temporarily overrides a FastAPI dependency and restores the previous value afterwards."""
    previous = app.dependency_overrides.get(dependency)
    app.dependency_overrides[dependency] = provider
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(dependency, None)
        else:
            app.dependency_overrides[dependency] = previous


def test_search_users_returns_user_map(test_client_no_auth, mock_db):
    mock_db.get_users.return_value = [
        Users(id=1, username="alpha", scopes=["admin"], hashed_password="hashed-alpha"),
        Users(id=2, username="beta", scopes=["user"], hashed_password="hashed-beta"),
    ]

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/search/users/")

    assert response.status_code == 200
    assert response.json() == {"items": {"alpha": 1, "beta": 2}}
    mock_db.get_users.assert_called_once_with()


def test_search_servers_returns_server_map(test_client_no_auth, mock_db):
    mock_db.get_server_list.return_value = [
        SimpleNamespace(id=101, name="survival"),
        SimpleNamespace(id=202, name="creative"),
    ]

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/search/servers/")

    assert response.status_code == 200
    assert response.json() == {"items": {"survival": 101, "creative": 202}}
    mock_db.get_server_list.assert_called_once_with(1)


def test_search_servers_missing_user_id_returns_400(test_client_no_auth, mock_db):
    mock_db.get_server_list.return_value = []
    missing_id_user = SimpleNamespace(id=None, admin=False)

    with (
        override_dependency(test_client_no_auth.app, get_db, lambda: mock_db),
        override_dependency(test_client_no_auth.app, auth_get_active_user, lambda: missing_id_user),
    ):
        response = test_client_no_auth.get("/search/servers/")

    assert response.status_code == 400
    assert response.json()["detail"] == "Failed to get current user ID"


def test_search_nodes_returns_node_map(test_client_no_auth, mock_db):
    mock_db.get_nodes.return_value = [
        SimpleNamespace(id=11, name="node-a"),
        SimpleNamespace(id=22, name="node-b"),
    ]

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/search/nodes/")

    assert response.status_code == 200
    assert response.json() == {"items": {"node-a": 11, "node-b": 22}}


def test_search_templates_returns_template_map(test_client_no_auth, mock_db):
    mock_db.get_templates.return_value = [
        SimpleNamespace(id=301, name="forge"),
        SimpleNamespace(id=302, name="fabric"),
    ]

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/search/templates/")

    assert response.status_code == 200
    assert response.json() == {"items": {"forge": 301, "fabric": 302}}


def test_search_fs_filters_results_to_exposed_paths(test_client_no_auth, mock_db, mocker):
    server = SimpleNamespace(container_name="server-container", template_id=55, name="test-server")
    template = SimpleNamespace(exposed_volume=["base/config", "shared"])
    mock_db.get_server.return_value = server
    mock_db.get_template.return_value = template

    docker_running = mocker.AsyncMock(return_value=True)
    list_directory = mocker.AsyncMock(
        return_value=(
            ["config/settings.cfg", "logs/output.log"],
            ["config", "hidden"],
        )
    )
    mocker.patch("server_manager.webservice.routes.search_api.docker_container_running", docker_running)
    mocker.patch("server_manager.webservice.routes.search_api.docker_list_directory", list_directory)

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/search/fs/1/base")

    assert response.status_code == 200
    assert response.json() == {"items": ["config/settings.cfg", "config/"]}
    docker_running.assert_awaited_once_with("server-container")
    list_directory.assert_awaited_once_with("server-container", "base")


def test_search_fs_returns_404_when_server_missing(test_client_no_auth, mock_db):
    mock_db.get_server.return_value = None

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/search/fs/99/root")

    assert response.status_code == 404
    assert response.json()["detail"] == "Server not found"


def test_search_fs_returns_400_when_container_stopped(test_client_no_auth, mock_db, mocker):
    server = SimpleNamespace(container_name="down-container", template_id=1, name="stopped")
    mock_db.get_server.return_value = server
    mocker.patch(
        "server_manager.webservice.routes.search_api.docker_container_running",
        mocker.AsyncMock(return_value=False),
    )

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/search/fs/1/root")

    assert response.status_code == 400
    assert response.json()["detail"] == "Container is not running"


def test_search_fs_returns_404_when_path_invalid(test_client_no_auth, mock_db, mocker):
    server = SimpleNamespace(container_name="server-container", template_id=55, name="test-server")
    template = SimpleNamespace(exposed_volume=["root"])
    mock_db.get_server.return_value = server
    mock_db.get_template.return_value = template

    mocker.patch(
        "server_manager.webservice.routes.search_api.docker_container_running",
        mocker.AsyncMock(return_value=True),
    )
    mocker.patch(
        "server_manager.webservice.routes.search_api.docker_list_directory",
        mocker.AsyncMock(return_value=None),
    )

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/search/fs/1/root")

    assert response.status_code == 404
    assert response.json()["detail"] == "Container not found or path invalid"


def test_search_fs_returns_500_when_template_missing(test_client_no_auth, mock_db, mocker):
    server = SimpleNamespace(container_name="server-container", template_id=55, name="test-server")
    mock_db.get_server.return_value = server
    mock_db.get_template.return_value = None

    mocker.patch(
        "server_manager.webservice.routes.search_api.docker_container_running",
        mocker.AsyncMock(return_value=True),
    )
    mocker.patch(
        "server_manager.webservice.routes.search_api.docker_list_directory",
        mocker.AsyncMock(return_value=([], [])),
    )

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/search/fs/1/root")

    assert response.status_code == 500
    assert response.json()["detail"] == "Template not found for server: test-server"
