# create a dev admin


from server_manager.webservice.db_models import Users
from server_manager.webservice.util.auth import get_password_hash
from server_manager.webservice.util.data_access import DB


def dev_startup():
    """Create a dev admin user if in dev mode and no users exist"""
    if not DB().get_user_by_username("admin"):
        # create dev data

        DB().create_user(
            Users(
                id=1,
                username="admin",
                disabled=False,
                admin=True,
                hashed_password=get_password_hash("admin"),
            )
        )
