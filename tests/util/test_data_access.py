# filepath: /home/wsl/Textual/server-manager/builder/SM-Backend/tests/util/test_data_access.py


import asyncio
import contextlib

import aiodocker
import pytest
import pytest_asyncio
from fastapi import HTTPException

from server_manager.webservice.db_models import (
    NodesCreate,
    ServersCreate,
    TemplatesCreate,
    UsersCreate,
)
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.singleton import SingletonMeta
from tests.mock_data import TEST_NODE, TEST_SERVER, TEST_TEMPLATE, TEST_USER

db_docker_image = "postgres:18"


@pytest.fixture(scope="session")
def monkeypatch_session():
    from _pytest.monkeypatch import MonkeyPatch

    m = MonkeyPatch()
    yield m
    m.undo()


async def delete_container_if_exists(client: aiodocker.Docker):
    """Helper to delete a docker image if it exists"""
    with contextlib.suppress(aiodocker.DockerError):
        if await client.containers.get("sm_test_db", silent=True):
            container = client.containers.container("sm_test_db")  # pragma: no cover
            await container.delete(force=True)  # pragma: no cover


@pytest_asyncio.fixture(scope="session")
async def db_container(monkeypatch_session):
    client = aiodocker.Docker()
    await client.pull(db_docker_image)
    await delete_container_if_exists(client)
    # port 5432
    container = await client.containers.create(
        {
            "Image": db_docker_image,
            "Tty": True,
            "OpenStdin": True,
            "HostConfig": {
                "PortBindings": {"5432/tcp": [{"HostPort": "5432"}]},
                "AutoRemove": True,
            },
            "Env": ["POSTGRES_USER=postgres", "POSTGRES_PASSWORD=postgres"],
        },
        name="sm_test_db",
    )
    await container.start()
    monkeypatch_session.setenv("SM_DB_CONNECTION", "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres")
    monkeypatch_session.setenv("SM_PORT_START", "27015")
    monkeypatch_session.setenv("SM_PORT_END", "27050")
    monkeypatch_session.setenv("SM_LOG_LEVEL", "DEBUG")

    await asyncio.sleep(2)  # wait for the db to be ready
    yield
    await container.delete(force=True, v=True)
    await client.close()


@pytest_asyncio.fixture(name="db_instance")
async def db_instance_fixture(db_container):  # noqa: ARG001 parameter shows dependency to pytest
    # Ensure a fresh singleton instance for each test
    SingletonMeta._instances.pop(DB, None)  # noqa: SLF001 # access protected member for testing purposes
    db = DB(verbose=True)
    yield db
    db.reset_database()


@pytest_asyncio.fixture(name="db_with_prereqs")
async def db_with_prereqs_fixture(db_instance: DB):
    """Provides a DB instance with a pre-created Node and Template."""
    db_instance.create_node(NodesCreate(**TEST_NODE))
    db_instance.create_template(TemplatesCreate(**TEST_TEMPLATE))
    yield db_instance


class TestDB:
    # Test for singleton behavior
    def test_singleton_instance(self, db_instance: DB):
        """Tests that the DB class is a singleton."""
        another_db_instance = DB()
        assert db_instance is another_db_instance

    # User tests
    def test_create_user(self, db_instance: DB):
        user_base = UsersCreate(username="testuser", scopes=[""], admin=False)
        user = db_instance.create_user(user_base, password="hashed")
        assert user.id is not None
        assert user.username == "testuser"
        assert not user.admin

    def test_get_user_by_username(self, db_instance: DB):
        user_base = UsersCreate(username="testuser", scopes=[""], admin=False)
        db_instance.create_user(
            user_base,
            password="hashed",
        )
        user = db_instance.lookup_username("testuser")
        assert user is not None
        assert user.username == "testuser"

    def test_get_user(self, db_instance: DB):
        user_base = UsersCreate(**TEST_USER)
        created_user = db_instance.create_user(user_base, password="hashed")
        retrieved_user = db_instance.get_user(created_user.id)
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id

    def test_delete_user(self, db_instance: DB):
        user_base = UsersCreate(**TEST_USER)
        user = db_instance.create_user(user_base, password="hashed")
        assert db_instance.delete_user(user.id)
        assert db_instance.get_user(user.id) is None
        assert not db_instance.delete_user(999)

    def test_get_users(self, db_instance: DB):
        db_instance.create_user(UsersCreate(**TEST_USER), password="hashed")
        db_instance.create_user(
            UsersCreate(**TEST_USER).model_copy(update={"username": "testuser2"}), password="hashed"
        )
        users = db_instance.get_users()
        assert len(users) == 2

    # Template tests
    def test_create_template(self, db_instance: DB):
        template_base = TemplatesCreate(**TEST_TEMPLATE)
        template = db_instance.create_template(template_base)
        assert template.id is not None
        assert template.name == "test-template"

    def test_create_existing_template_raises_error(self, db_instance: DB):
        template_base = TemplatesCreate(**TEST_TEMPLATE)
        db_instance.create_template(template_base)
        with pytest.raises(HTTPException) as excinfo:
            db_instance.create_template(template_base)
        assert excinfo.value.status_code == 422
        assert isinstance(excinfo.value.detail, dict)
        assert excinfo.value.detail.get("error") == "TemplateExists"

    def test_get_template(self, db_instance: DB):
        template_base = TemplatesCreate(**TEST_TEMPLATE)
        created_template = db_instance.create_template(template_base)
        assert created_template.id is not None
        retrieved_template = db_instance.get_template(created_template.id)
        assert retrieved_template is not None
        assert retrieved_template.id == created_template.id

    def test_get_templates(self, db_instance: DB):
        db_instance.create_template(TemplatesCreate(**TEST_TEMPLATE))
        other_template = TemplatesCreate(**TEST_TEMPLATE).model_copy(update={"name": "t2", "description": "d2"})
        db_instance.create_template(other_template)
        templates = db_instance.get_templates()
        assert len(templates) == 2

    def test_update_template(self, db_instance: DB):
        template_base = TemplatesCreate(**TEST_TEMPLATE)
        template = db_instance.create_template(template_base)
        updated_base = TemplatesCreate(**TEST_TEMPLATE).model_copy(
            update={"name": "updated-template", "description": "Updated desc"}
        )
        assert template.id is not None
        updated_base = TemplatesCreate(**TEST_TEMPLATE).model_copy(
            update={"name": "updated-template", "description": "Updated desc"}
        )
        updated_template = db_instance.update_template(template.id, updated_base)
        assert updated_template is not None
        assert updated_template.name == "updated-template"
        assert updated_template.description == "Updated desc"

    def test_delete_template(self, db_instance: DB):
        template_base = TemplatesCreate(**TEST_TEMPLATE)
        template = db_instance.create_template(template_base)
        assert template.id is not None
        assert db_instance.delete_template(template.id)
        assert db_instance.get_template(template.id) is None
        assert not db_instance.delete_template(999)

    # Node tests
    def test_create_node(self, db_instance: DB):
        node_base = NodesCreate(**TEST_NODE)
        node = db_instance.create_node(node_base)
        assert node.id is not None
        assert node.name == "test-node"

    def test_get_node(self, db_instance: DB):
        node_base = NodesCreate(**TEST_NODE)
        created_node = db_instance.create_node(node_base)
        retrieved_node = db_instance.get_node(created_node.id)
        assert retrieved_node is not None
        assert retrieved_node.id == created_node.id

    def test_get_nodes(self, db_instance: DB):
        db_instance.create_node(NodesCreate(**TEST_NODE))
        other_node = NodesCreate(**TEST_NODE).model_copy(update={"name": "n2"})
        db_instance.create_node(other_node)
        nodes = db_instance.get_nodes()
        assert len(nodes) == 2

    def test_delete_node(self, db_instance: DB):
        node_base = NodesCreate(**TEST_NODE)
        node = db_instance.create_node(node_base)
        assert db_instance.delete_node(node.id)
        assert db_instance.get_node(node.id) is None
        assert not db_instance.delete_node(999)

    # Server tests
    def test_create_server(self, db_with_prereqs: DB):
        server_base = ServersCreate(**TEST_SERVER)
        server = db_with_prereqs.create_server(server_base, port=[27015])
        assert server.id is not None
        assert server.name == "test-server"

    def test_get_server(self, db_with_prereqs: DB):
        server_base = ServersCreate(**TEST_SERVER)
        created_server = db_with_prereqs.create_server(server_base, port=[27015])
        assert created_server.id is not None
        retrieved_server = db_with_prereqs.get_server(created_server.id)
        assert retrieved_server is not None
        assert retrieved_server.id == created_server.id

    def test_get_server_by_name(self, db_with_prereqs: DB):
        server_base = ServersCreate(**TEST_SERVER)
        db_with_prereqs.create_server(server_base, port=[27015])
        server = db_with_prereqs.get_server_by_name("test-server")
        assert server is not None
        assert server.name == "test-server"

    def test_delete_server(self, db_with_prereqs: DB):
        server_base = ServersCreate(**TEST_SERVER)
        server = db_with_prereqs.create_server(server_base, port=[27015])
        assert server.id is not None
        assert db_with_prereqs.delete_server(server.id)
        assert db_with_prereqs.get_server(server.id) is None
        assert not db_with_prereqs.delete_server(999)

    def test_get_server_list_admin(self, db_with_prereqs: DB):
        server_base = ServersCreate(**TEST_SERVER)
        UsersCreate(**TEST_USER).model_copy(update={"admin": True, "username": "1"})
        db_with_prereqs.create_server(server_base, port=[27015])
        db_with_prereqs.create_server(
            server_base.model_copy(update={"name": "s2", "container_name": "c2"}), port=[27016]
        )
        servers = db_with_prereqs.get_all_servers()
        assert len(servers) == 2

    def test_get_server_list_non_admin(self, db_with_prereqs: DB):
        server_base = ServersCreate(**TEST_SERVER)
        user = UsersCreate(**TEST_USER).model_copy(update={"admin": False, "username": "v1"})
        user_obj = db_with_prereqs.create_user(user, password="hashed")
        assert user_obj
        server1 = db_with_prereqs.create_server(server_base, port=[27015])
        db_with_prereqs.create_server(
            server_base.model_copy(update={"name": "s2", "container_name": "c2"}), port=[27016]
        )
        db_with_prereqs.add_user_to_server(server1.id, user_obj.id)
        servers = db_with_prereqs.get_server_list(owner_id=user_obj.id)
        assert len(servers) == 1, f"Expected 1 server, got {len(servers)}"
        assert servers[0].id == server1.id

    def test_unused_port(self, db_with_prereqs: DB):
        ports = db_with_prereqs.unused_port(5)
        assert ports == [27015, 27016, 27017, 27018, 27019]

        db_with_prereqs.create_server(ServersCreate(**TEST_SERVER), port=db_with_prereqs.unused_port(1))
        assert db_with_prereqs.unused_port(5) == [27016, 27017, 27018, 27019, 27020]
