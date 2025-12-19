"""
data_access.py

Database access layer using SQLModel and Singleton pattern

Author: Nathan Swanson
"""

import os
from collections.abc import Generator, Sequence
from typing import Any, cast

import sqlalchemy
import sqlalchemy.exc
import sqlmodel
from fastapi import HTTPException
from psycopg2.errors import UniqueViolation
from pydantic import ValidationError
from sqlalchemy.exc import InvalidRequestError
from sqlmodel import Session, SQLModel, create_engine, func, select

from server_manager.webservice.db_models import (
    Nodes,
    NodesCreate,
    NodesRead,
    Servers,
    ServersCreate,
    ServersRead,
    Templates,
    TemplatesCreate,
    TemplatesRead,
    Users,
    UsersCreate,
    UsersRead,
)
from server_manager.webservice.util.singleton import SingletonMeta


class DB(metaclass=SingletonMeta):
    def __init__(self, verbose: bool = False):
        self._engine = create_engine(os.environ["SM_DB_CONNECTION"], echo=verbose)

        SQLModel.metadata.create_all(self._engine)

    def unused_port(self, count: int = 1) -> list[int] | None:
        with Session(self._engine) as session:
            all_ports = select(
                func.generate_series(int(os.environ["SM_PORT_START"]), int(os.environ["SM_PORT_END"])).label("port")
            ).subquery("all_ports")

            # Build a scalar subquery of used ports to avoid a CompoundSelect in the final statement
            used_ports_scalar = select(func.unnest(Servers.port)).scalar_subquery()

            # Use a plain SELECT with a NOT IN subquery instead of EXCEPT to satisfy typing for Session.exec
            statement = (
                select(all_ports.c.port)
                .where(~all_ports.c.port.in_(used_ports_scalar))
                .order_by(all_ports.c.port)
                .limit(count)
            )

            rows = session.exec(statement).all()
            return list(rows)

        return None

    # server
    def create_server(self, server: ServersCreate, **kwargs) -> ServersRead:
        with Session(self._engine) as session:
            db_server = Servers.model_validate(server, update=kwargs)
            session.add(db_server)
            session.commit()
            session.refresh(db_server)
            return cast(ServersRead, db_server)

    def get_server(self, server_id: int) -> ServersRead | None:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Servers).where(Servers.id == server_id)
            server = session.exec(statement).first()
            return cast(ServersRead | None, server)

    def get_server_by_name(self, name: str) -> ServersRead | None:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Servers).where(Servers.name == name)
            server = session.exec(statement).first()
            return cast(ServersRead | None, server)

    def get_all_servers(self) -> Sequence[ServersRead]:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Servers)
            return cast(Sequence[ServersRead], session.exec(statement).all())

    def get_server_list(self, owner_id: int) -> list[ServersRead]:
        with Session(self._engine) as session:
            user_obj = session.get(Users, owner_id)

            if user_obj is None:
                return []
            return cast(list[ServersRead], user_obj.linked_servers)

    def add_user_to_server(self, server_id: int, user_id: int) -> None:
        with Session(self._engine) as session:
            server_obj = session.get(Servers, server_id)
            if server_obj is None:
                raise HTTPException(status_code=404, detail="Server not found")

            user_obj = session.get(Users, user_id)
            if user_obj is None:
                raise HTTPException(status_code=404, detail="User not found")
            server_obj.linked_users.append(user_obj)
            session.add(server_obj)
            session.commit()

    def delete_server(self, server_id: int) -> bool:
        with Session(self._engine) as session:
            server_obj = session.get(Servers, server_id)
            if server_obj is not None:
                session.delete(server_obj)
                session.commit()
                return True
        return False

    # user
    def create_user(self, user: UsersCreate, password: str) -> UsersRead:
        with Session(self._engine) as session:
            db_user = Users.model_validate(user, update={"hashed_password": password})
            db_user.admin = False  # admins must be added manually
            session.add(db_user)
            session.commit()
            session.refresh(db_user)
            return cast(UsersRead, db_user)

    def lookup_username(self, username: str) -> Users | None:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Users).where(Users.username == username)
            return session.exec(statement).first()

    def get_user(self, user_id: int, full_data: bool = False) -> UsersRead | Users | None:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Users).where(Users.id == user_id)
            return (
                cast(UsersRead | None, session.exec(statement).first())
                if full_data is False
                else session.get(Users, user_id)
            )

    def delete_user(self, user_id: int) -> bool:
        with Session(self._engine) as session:
            user_obj = session.get(Users, user_id)
            if user_obj is not None:
                session.delete(user_obj)
                session.commit()
                return True
        return False

    # template

    def create_template(
        self,
        template: TemplatesCreate,
    ) -> TemplatesRead:
        with Session(self._engine) as session:
            try:
                mapped_template = Templates.model_validate(template)
                session.add(mapped_template)
                session.commit()
                session.refresh(mapped_template)
            except sqlalchemy.exc.IntegrityError as e:
                if isinstance(e.orig, UniqueViolation):
                    raise HTTPException(
                        status_code=422, detail={"error": "TemplateExists", "message": "Template already exists"}
                    ) from e
                raise HTTPException(status_code=500, detail="failed to create template") from e
            except ValidationError as e:
                raise HTTPException(status_code=500, detail=f"failed to validate Template error: {e}") from e
            return cast(TemplatesRead, mapped_template)

    def get_template(self, template_id: int) -> Templates | None:
        with Session(self._engine) as session:
            return session.get(Templates, template_id)

    def get_templates(self) -> Sequence[TemplatesRead]:
        with Session(self._engine) as session:
            return cast(Sequence[TemplatesRead], session.exec(sqlmodel.select(Templates)).all())

    def update_template(self, template_id: int, template: TemplatesCreate) -> Templates | None:
        with Session(self._engine) as session:
            template_obj = session.get(Templates, template_id)
            if template_obj is not None:
                try:
                    updated_template = template.model_copy()
                    for key, value in updated_template.model_dump().items():
                        setattr(template_obj, key, value)
                    session.add(template_obj)
                    session.commit()
                    session.refresh(template_obj)
                except (sqlalchemy.exc.IntegrityError, ValidationError):
                    return None
                else:
                    return template_obj
        return None

    def delete_template(self, template_id: int) -> bool:
        with Session(self._engine) as session:
            template_obj = session.get(Templates, template_id)
            if template_obj is not None:
                try:
                    session.delete(template_obj)
                    session.commit()
                except InvalidRequestError:
                    return False
                else:
                    return True
        return False

    # node

    def create_node(self, node: NodesCreate) -> NodesRead:
        with Session(self._engine) as session:
            mapped_node = Nodes.model_validate(node)
            session.add(mapped_node)
            session.commit()
            session.refresh(mapped_node)
            return cast(NodesRead, mapped_node)

    def get_node(self, node_id: int) -> NodesRead | None:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Nodes).where(Nodes.id == node_id)
            return cast(NodesRead | None, session.exec(statement).first())

    def get_nodes(self) -> Sequence[NodesRead]:
        statement = sqlmodel.select(Nodes)
        with Session(self._engine) as session:
            return cast(Sequence[NodesRead], session.exec(statement).all())

    def get_users(self) -> Sequence[UsersRead]:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Users)
            return cast(Sequence[UsersRead], session.exec(statement).all())

    def delete_node(self, node_id: int) -> bool:
        with Session(self._engine) as session:
            node_obj = session.get(Nodes, node_id)
            if node_obj is not None:
                session.delete(node_obj)
                session.commit()
                return True
        return False

    def reset_database(self):
        sqlmodel.SQLModel.metadata.drop_all(self._engine)


def get_db() -> Generator[DB, Any, None]:
    db = DB()
    try:
        yield db
    finally:
        pass
