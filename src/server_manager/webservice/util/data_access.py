from collections.abc import Sequence

import sqlalchemy.exc
import sqlmodel
from sqlmodel import Session, SQLModel, create_engine

from server_manager.webservice.db_models import Template, User
from server_manager.webservice.util.singleton import SingletonMeta

sqlite_file_name = "dev.db"
sqlite_url = f"sqlite:///../db/{sqlite_file_name}"


class DB(metaclass=SingletonMeta):
    def __init__(self):
        self._engine = create_engine(sqlite_url, echo=True)
        SQLModel.metadata.create_all(self._engine)

    def create_user(self, user: User) -> User:
        with Session(self._engine) as session:
            user.admin = False  # admins must be added manually
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def get_user_by_username(self, username: str) -> User | None:
        with Session(self._engine) as session:
            return session.get(User, username)

    def delete_user(self, user: User | str) -> bool:
        with Session(self._engine) as session:
            user_obj = user if isinstance(user, User) else session.get(User, user)
            if user_obj is not None:
                session.delete(user_obj)
                return True
        return False

    def get_template_by_name(self, template_name: str) -> Template | None:
        with Session(self._engine) as session:
            return session.get(Template, template_name)

    def get_template_name_list(self) -> Sequence[str]:
        with Session(self._engine) as session:
            return session.exec(sqlmodel.select(Template.name)).all()

    def create_template(self, template: Template):
        with Session(self._engine) as session:
            session.add(template)
            session.commit()
            session.refresh(template)
            return template

    def delete_template(self, template: Template | str) -> bool:
        with Session(self._engine) as session:
            template_obj = session.get(Template, template)
            if template_obj is not None:
                try:
                    session.delete(template_obj)
                    session.commit()
                except sqlalchemy.exc.InvalidRequestError:
                    return False
                else:
                    return True
        return False
