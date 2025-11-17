from contextlib import contextmanager
from types import SimpleNamespace

from server_manager.webservice.db_models import NodesRead
from server_manager.webservice.util.data_access import get_db
from tests.mock_data import TEST_NODE


@contextmanager
def override_dependency(app, dependency, provider):
    previous = app.dependency_overrides.get(dependency)
    app.dependency_overrides[dependency] = provider
    try:
        yield
    finally:
        if previous is None:
            app.dependency_overrides.pop(dependency, None)
        else:
            app.dependency_overrides[dependency] = previous


def test_add_node_returns_created_node(test_client_no_auth, mock_db):
    created = NodesRead(**TEST_NODE, id=42)
    mock_db.create_node.return_value = created

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.post("/nodes/", json=TEST_NODE)

    assert response.status_code == 200
    assert response.json() == created.model_dump()
    mock_db.create_node.assert_called_once()


def test_get_node_returns_existing_node(test_client_no_auth, mock_db):
    node = NodesRead(**TEST_NODE, id=7)
    mock_db.get_node.return_value = node

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/nodes/7")

    assert response.status_code == 200
    assert response.json() == node.model_dump()
    mock_db.get_node.assert_called_once_with(7)


def test_get_node_missing_returns_404(test_client_no_auth, mock_db):
    mock_db.get_node.return_value = None

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/nodes/55")

    assert response.status_code == 404
    assert response.json()["detail"] == "Node not found"


def test_disk_usage_parses_df_output(test_client_no_auth, mocker):
    mock_run = mocker.patch(
        "server_manager.webservice.routes.nodes_api.subprocess.run",
        return_value=SimpleNamespace(stdout=b"Filesystem\nline\ntotal 100 200 300 40% /"),
    )

    response = test_client_no_auth.get("/nodes/1/disk_usage")

    assert response.status_code == 200
    assert response.json() == {"used": 200, "total": 300}
    mock_run.assert_called_once()


def test_disk_usage_handles_missing_stdout(test_client_no_auth, mocker):
    mocker.patch(
        "server_manager.webservice.routes.nodes_api.subprocess.run",
        return_value=SimpleNamespace(stdout=None),
    )

    response = test_client_no_auth.get("/nodes/1/disk_usage")

    assert response.status_code == 200
    assert response.json() == {"used": -1, "total": -1}


def test_runtime_returns_hours(test_client_no_auth, mocker):
    mocker.patch(
        "server_manager.webservice.routes.nodes_api.subprocess.run",
        return_value=SimpleNamespace(stdout=b"12:34:56 up 2 days, 05:12, 3 users, load average: 0.10, 0.20, 0.30"),
    )

    response = test_client_no_auth.get("/nodes/1/runtime")

    assert response.status_code == 200
    assert response.json() == {"uptime_hours": 53}


def test_runtime_returns_negative_when_pattern_missing(test_client_no_auth, mocker):
    mocker.patch(
        "server_manager.webservice.routes.nodes_api.subprocess.run",
        return_value=SimpleNamespace(stdout=b"unexpected output"),
    )

    response = test_client_no_auth.get("/nodes/1/runtime")

    assert response.status_code == 200
    assert response.json() == {"uptime_hours": -1}
