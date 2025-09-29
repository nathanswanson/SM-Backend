"""
data_access.py

Database access layer using SQLModel and Singleton pattern

Author: Nathan Swanson
"""

import os
from collections.abc import Sequence

import sqlalchemy.exc
import sqlmodel
from sqlmodel import Session, SQLModel, create_engine

from server_manager.webservice.db_models import Nodes, Templates, Users
from server_manager.webservice.util.singleton import SingletonMeta


class DB(metaclass=SingletonMeta):
    def __init__(self):
        self._engine = create_engine(os.environ["SM_DB_CONNECTION"], echo=True)
        SQLModel.metadata.create_all(self._engine)

    def create_user(self, user: Users) -> Users:
        if (existing_user := self.get_user_by_username(user.username)) is not None:
            return existing_user
        with Session(self._engine) as session:
            user.admin = False  # admins must be added manually
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def get_user_by_username(self, username: str) -> Users | None:
        with Session(self._engine) as session:
            return session.get(Users, username)

    def delete_user(self, user: Users | str) -> bool:
        with Session(self._engine) as session:
            user_obj = user if isinstance(user, Users) else session.get(Users, user)
            if user_obj is not None:
                session.delete(user_obj)
                return True
        return False

    def get_template_by_name(self, template_name: str) -> Templates | None:
        with Session(self._engine) as session:
            return session.get(Templates, template_name)

    def get_template_name_list(self) -> Sequence[str]:
        with Session(self._engine) as session:
            return session.exec(sqlmodel.select(Templates.name)).all()

    def create_template(self, template: Templates):
        with Session(self._engine) as session:
            session.add(template)
            session.commit()
            session.refresh(template)
            return template

    def delete_template(self, template: Templates | str) -> bool:
        with Session(self._engine) as session:
            template_obj = session.get(Templates, template)
            if template_obj is not None:
                try:
                    session.delete(template_obj)
                    session.commit()
                except sqlalchemy.exc.InvalidRequestError:
                    return False
                else:
                    return True
        return False

    def get_node(self, node_id: str):
        with Session(self._engine) as session:
            return session.get(Nodes, node_id)
