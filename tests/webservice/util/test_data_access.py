from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import InvalidRequestError

from server_manager.webservice.db_models import UsersCreate
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


# filepath: /home/wsl/Textual/server-manager/builder/SM-Backend/tests/util/test_data_access.py
