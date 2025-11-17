from contextlib import contextmanager

from server_manager.webservice.db_models import TemplatesRead
from server_manager.webservice.util.data_access import get_db
from tests.mock_data import TEST_TEMPLATE, TEST_TEMPLATE_READ


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


def test_add_template_success(test_client_no_auth, mock_db, mocker):
    mocker.patch("server_manager.webservice.routes.template_api.docker_image_exposed_port", return_value=[25565])
    mock_db.create_template.return_value = TemplatesRead(**TEST_TEMPLATE_READ).model_copy(update={"id": 5})

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.post("/templates/", json=TEST_TEMPLATE)

    assert response.status_code == 200
    assert response.json() == {"success": True}
    mock_db.create_template.assert_called_once()


def test_add_template_returns_false_when_db_fails(test_client_no_auth, mock_db, mocker):
    mocker.patch("server_manager.webservice.routes.template_api.docker_image_exposed_port", return_value=[25565])
    mock_db.create_template.return_value = None

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.post("/templates/", json=TEST_TEMPLATE)

    assert response.status_code == 200
    assert response.json() == {"success": False}


def test_get_template_success(test_client_no_auth, mock_db):
    template = TemplatesRead(**TEST_TEMPLATE_READ).model_copy(update={"id": 10})
    mock_db.get_template.return_value = template

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/templates/10")

    assert response.status_code == 200
    assert response.json() == template.model_dump()


def test_get_template_missing_returns_404(test_client_no_auth, mock_db):
    mock_db.get_template.return_value = None

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.get("/templates/22")

    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found"


def test_update_template_success(test_client_no_auth, mock_db, mocker):
    mocker.patch("server_manager.webservice.routes.template_api.docker_image_exposed_port", return_value=[25565])
    mock_db.update_template.return_value = TemplatesRead(**TEST_TEMPLATE_READ).model_copy(update={"id": 10})

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.patch("/templates/10", json=TEST_TEMPLATE)

    assert response.status_code == 200
    assert response.json() == {"success": True}


def test_update_template_failure_returns_false(test_client_no_auth, mock_db, mocker):
    mocker.patch("server_manager.webservice.routes.template_api.docker_image_exposed_port", return_value=[25565])
    mock_db.update_template.return_value = None

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.patch("/templates/10", json=TEST_TEMPLATE)

    assert response.status_code == 200
    assert response.json() == {"success": False}


def test_delete_template_propagates_result(test_client_no_auth, mock_db):
    mock_db.delete_template.return_value = True

    with override_dependency(test_client_no_auth.app, get_db, lambda: mock_db):
        response = test_client_no_auth.delete("/templates/5/delete", params={"template_id": 5})

    assert response.status_code == 200
    assert response.json() == {"success": True}
    mock_db.delete_template.assert_called_once_with(5)
