"""
data_access.py

Database access layer using SQLModel and Singleton pattern

Author: Nathan Swanson
"""

import os
from collections.abc import Sequence
from typing import cast

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
    NodesBase,
    NodesRead,
    Servers,
    ServersBase,
    ServersRead,
    ServerUserLink,
    Templates,
    TemplatesBase,
    TemplatesRead,
    Users,
    UsersBase,
    UsersRead,
)
from server_manager.webservice.util.singleton import SingletonMeta


class DB(metaclass=SingletonMeta):
    def __init__(self):
        self._engine = create_engine(os.environ["SM_DB_CONNECTION"])

        SQLModel.metadata.create_all(self._engine)

    def create(self, obj: Servers | Users | Templates | Nodes):
        with Session(self._engine) as session:
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj

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
    def create_server(self, server: ServersBase, **kwargs) -> Servers:
        with Session(self._engine) as session:
            server = Servers.model_validate(server, update=kwargs)
            session.add(server)
            session.commit()
            session.refresh(server)
            return server

    def get_server(self, server_id: int) -> Servers | None:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Servers).where(Servers.id == server_id)
            return session.exec(statement).first()

    def get_server_by_name(self, name: str) -> Servers | None:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Servers).where(Servers.name == name)
            return session.exec(statement).first()

    def get_server_list(self, owner: Users) -> Sequence[ServersRead]:
        with Session(self._engine) as session:
            # if admin just give every one
            if owner.admin:
                statement = sqlmodel.select(Servers)
            else:
                statement = sqlmodel.select(Servers).join(ServerUserLink).where(ServerUserLink.user_id == owner.id)
            return cast(Sequence[ServersRead], session.exec(statement).all())

    def delete_server(self, server_id: int) -> bool:
        with Session(self._engine) as session:
            server_obj = session.get(Servers, server_id)
            if server_obj is not None:
                session.delete(server_obj)
                session.commit()
                return True
        return False

    # user
    def create_user(self, user: UsersBase | Users) -> UsersRead:
        with Session(self._engine) as session:
            user.admin = False  # admins must be added manually
            user = Users.model_validate(user)
            session.add(user)
            session.commit()
            session.refresh(user)
            return cast(UsersRead, user)

    def get_user_by_username(self, username: str) -> Users | None:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Users).where(Users.username == username)
            return cast(Users | None, session.exec(statement).first())

    def get_user(self, user_id: int) -> UsersRead | None:
        with Session(self._engine) as session:
            statement = sqlmodel.select(Users).where(Users.id == user_id)
            return cast(UsersRead | None, session.exec(statement).first())

    def delete_user(self, user_id: int) -> bool:
        with Session(self._engine) as session:
            user_obj = session.get(Users, user_id)
            if user_obj is not None:
                session.delete(user_obj)
                return True
        return False

    # template

    def create_template(
        self,
        template: TemplatesBase,
        **kwargs,
    ):
        with Session(self._engine) as session:
            try:
                mapped_template = Templates.model_validate(template, update=kwargs)
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
            return mapped_template

    def get_template(self, template_id: int) -> Templates | None:
        with Session(self._engine) as session:
            return session.get(Templates, template_id)

    def get_templates(self) -> Sequence[TemplatesRead]:
        with Session(self._engine) as session:
            return cast(Sequence[TemplatesRead], session.exec(sqlmodel.select(Templates)).all())

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

    def create_node(self, node: NodesBase) -> NodesRead:
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
                return True
        return False

    def exec_raw(self, query: str):
        if self._engine.dialect.name == "sqlite":
            conn = self._engine.raw_connection()
            try:
                cursor = conn.cursor()
                cursor.executescript(query)
                conn.commit()
            finally:
                conn.close()
