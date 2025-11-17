from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from server_manager.webservice.db_models import NodesCreate, ServersCreate, TemplatesCreate, UsersCreate
from server_manager.webservice.util.data_access import DB, get_db
from server_manager.webservice.util.singleton import SingletonMeta


class _SessionContext:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def reset_singleton():
    SingletonMeta._instances.pop(DB, None)  # noqa: SLF001 - reset singleton state for tests
    yield
    SingletonMeta._instances.pop(DB, None)  # noqa: SLF001 - cleanup after tests


@pytest.fixture
def db_with_session(mocker, monkeypatch):
    monkeypatch.setenv("SM_DB_CONNECTION", "sqlite:///:memory:")
    monkeypatch.setenv("SM_PORT_START", "27015")
    monkeypatch.setenv("SM_PORT_END", "27020")

    engine = object()
    mocker.patch("server_manager.webservice.util.data_access.create_engine", return_value=engine)
    mocker.patch("server_manager.webservice.util.data_access.SQLModel.metadata.create_all")
    drop_all = mocker.patch("server_manager.webservice.util.data_access.sqlmodel.SQLModel.metadata.drop_all")

    session = mocker.MagicMock()
    mocker.patch("server_manager.webservice.util.data_access.Session", return_value=_SessionContext(session))

    db = DB()
    return db, session, engine, drop_all


def test_create_user_forces_non_admin(db_with_session):
    db, session, *_ = db_with_session
    session.refresh.side_effect = lambda obj: setattr(obj, "id", 99)

    user = db.create_user(UsersCreate(username="root", scopes=["*"], admin=True), password="hashed")

    assert user.id == 99
    assert user.admin is False
    session.add.assert_called_once_with(user)


def test_unused_port_returns_available_ports(db_with_session, mocker):
    db, session, *_ = db_with_session
    exec_result = mocker.MagicMock()
    exec_result.all.return_value = [27015, 27016]
    session.exec.return_value = exec_result

    assert db.unused_port(2) == [27015, 27016]
    session.exec.assert_called_once()


def test_get_server_list_returns_linked_servers(db_with_session):
    db, session, *_ = db_with_session
    linked = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    session.get.return_value = SimpleNamespace(linked_servers=linked)

    servers = db.get_server_list(owner_id=10)

    assert servers == linked
    session.get.assert_called_once()


def test_get_server_list_returns_empty_when_user_missing(db_with_session):
    db, session, *_ = db_with_session
    session.get.return_value = None

    assert db.get_server_list(owner_id=10) == []


def test_add_user_to_server_raises_when_server_missing(db_with_session):
    db, session, *_ = db_with_session
    session.get.return_value = None

    with pytest.raises(HTTPException) as exc:
        db.add_user_to_server(server_id=1, user_id=2)

    assert exc.value.detail == "Server not found"


def test_add_user_to_server_raises_when_user_missing(db_with_session):
    db, session, *_ = db_with_session
    server_obj = SimpleNamespace(linked_users=[])
    session.get.side_effect = [server_obj, None]

    with pytest.raises(HTTPException) as exc:
        db.add_user_to_server(server_id=1, user_id=2)

    assert exc.value.detail == "User not found"


def test_add_user_to_server_appends_and_commits(db_with_session):
    db, session, *_ = db_with_session
    user_obj = SimpleNamespace(id=2)
    server_obj = SimpleNamespace(linked_users=[])
    session.get.side_effect = [server_obj, user_obj]

    db.add_user_to_server(server_id=1, user_id=2)

    assert user_obj in server_obj.linked_users
    session.add.assert_called_once_with(server_obj)
    session.commit.assert_called_once()


def test_delete_template_returns_false_on_invalid_request(db_with_session):
    db, session, *_ = db_with_session
    session.get.return_value = object()
    session.delete.side_effect = InvalidRequestError("bad delete")

    assert db.delete_template(template_id=42) is False


def test_delete_template_returns_true_on_success(db_with_session):
    db, session, *_ = db_with_session
    session.get.return_value = object()

    assert db.delete_template(template_id=42) is True
    session.delete.assert_called_once()
    session.commit.assert_called_once()


def test_reset_database_drops_all(db_with_session):
    db, _, engine, drop_all = db_with_session

    db.reset_database()

    drop_all.assert_called_once_with(engine)


def test_get_db_yields_singleton_instance(db_with_session):
    db, *_ = db_with_session

    generator = get_db()
    yielded = next(generator)

    assert yielded is db
    with pytest.raises(StopIteration):
        next(generator)


def _sample_server_payload():
    return ServersCreate(
        name="srv",
        env={"A": "1"},
        cpu=1,
        disk=10,
        memory=2,
        container_name="srv-container",
        node_id=1,
        template_id=2,
        tags=["prod"],
    )


def _sample_template_payload():
    return TemplatesCreate(
        name="temp",
        image="repo/image:latest",
        tags=["latest"],
        exposed_port=[25565],
        exposed_volume=["/data"],
        modules=["base"],
        description="desc",
        resource_min_cpu=1,
        resource_min_disk=10,
        resource_min_mem=2,
    )


def _sample_node_payload():
    return NodesCreate(
        name="node",
        cpus=8,
        disk=100,
        memory=32,
        cpu_name="Test CPU",
        max_hz=3600,
        arch="x86_64",
    )


def _template_validation_error() -> ValidationError:
    try:
        TemplatesCreate(  # type: ignore[arg-type]
            name="temp",
            image="repo/image:latest",
            tags="invalid",
            exposed_port=[25565],
            exposed_volume=["/data"],
            modules=None,
        )
    except ValidationError as exc:
        return exc
    raise AssertionError("Expected TemplatesCreate validation to fail")


def test_create_server_returns_refreshed_instance(db_with_session):
    db, session, *_ = db_with_session
    session.refresh.side_effect = lambda obj: setattr(obj, "id", 7)

    created = db.create_server(_sample_server_payload(), port=[25000, 25001])

    assert created.id == 7
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_get_server_and_server_by_name_use_exec(db_with_session):
    db, session, *_ = db_with_session
    sentinel = SimpleNamespace(id=5)
    exec_result = session.exec.return_value
    exec_result.first.return_value = sentinel

    assert db.get_server(1) is sentinel
    exec_result.first.return_value = None
    assert db.get_server_by_name("srv") is None


def test_get_all_servers_returns_sequence(db_with_session):
    db, session, *_ = db_with_session
    session.exec.return_value.all.return_value = [1, 2]

    assert db.get_all_servers() == [1, 2]


def test_delete_server_true_and_false(db_with_session):
    db, session, *_ = db_with_session
    session.get.side_effect = [object(), None]

    assert db.delete_server(1) is True
    assert db.delete_server(2) is False


def test_lookup_and_get_user_variants(db_with_session):
    db, session, *_ = db_with_session
    user = SimpleNamespace(id=1)
    exec_result = session.exec.return_value
    exec_result.first.return_value = user

    assert db.lookup_username("name") is user
    session.exec.return_value.first.return_value = None
    session.get.return_value = user
    assert db.get_user(1, full_data=True) is user


def test_delete_user_branching(db_with_session):
    db, session, *_ = db_with_session
    session.get.side_effect = [object(), None]

    assert db.delete_user(1) is True
    assert db.delete_user(2) is False


def test_create_template_handles_unique_violation(db_with_session, mocker, monkeypatch):
    db, session, *_ = db_with_session

    class DummyUniqueViolation(Exception):
        pass

    monkeypatch.setattr("server_manager.webservice.util.data_access.UniqueViolation", DummyUniqueViolation)
    session.add.side_effect = IntegrityError("", {}, DummyUniqueViolation())

    with pytest.raises(HTTPException) as exc:
        db.create_template(_sample_template_payload())

    assert exc.value.status_code == 422


def test_create_template_handles_other_integrity_error(db_with_session):
    db, session, *_ = db_with_session
    session.add.side_effect = IntegrityError("", {}, Exception("boom"))

    with pytest.raises(HTTPException) as exc:
        db.create_template(_sample_template_payload())

    assert exc.value.status_code == 500


def test_create_template_handles_validation_error(db_with_session, mocker):
    db, session, *_ = db_with_session
    mocker.patch(
        "server_manager.webservice.util.data_access.Templates.model_validate",
        side_effect=_template_validation_error(),
    )

    with pytest.raises(HTTPException) as exc:
        db.create_template(_sample_template_payload())

    assert exc.value.status_code == 500


def test_update_template_success_and_failure(db_with_session, mocker):
    db, session, *_ = db_with_session
    template_obj = SimpleNamespace(name="temp")
    session.get.return_value = template_obj
    template = _sample_template_payload()

    updated = db.update_template(1, template, description="new")

    assert updated is template_obj
    session.add.assert_called()

    mocker.patch(
        "server_manager.webservice.util.data_access.TemplatesCreate.model_copy",
        side_effect=_template_validation_error(),
    )

    assert db.update_template(1, template, description="other") is None


def test_delete_template_handles_invalid_request(db_with_session):
    db, session, *_ = db_with_session
    template_obj = object()
    session.get.return_value = template_obj
    session.delete.side_effect = InvalidRequestError("bad")

    assert db.delete_template(1) is False


def test_delete_template_success(db_with_session):
    db, session, *_ = db_with_session
    template_obj = object()
    session.get.return_value = template_obj

    assert db.delete_template(1) is True


def test_node_helpers_cover_all_branches(db_with_session):
    db, session, *_ = db_with_session
    session.exec.return_value.all.return_value = [1]
    session.get.side_effect = [object(), None]

    node = db.create_node(_sample_node_payload())
    assert node is not None

    session.exec.return_value.first.return_value = node
    assert db.get_node(1) is node
    assert db.get_nodes() == [1]
    session.exec.return_value.all.return_value = ["user"]
    assert db.get_users() == ["user"]
    assert db.delete_node(1) is True
    assert db.delete_node(2) is False


# filepath: /home/wsl/Textual/server-manager/builder/SM-Backend/tests/util/test_data_access.py
