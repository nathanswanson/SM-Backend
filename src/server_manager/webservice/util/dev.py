# create a dev admin
import os

import socketio
from colorama import Fore

from server_manager.webservice.db_models import Users
from server_manager.webservice.logger import sm_logger
from server_manager.webservice.util.auth import get_password_hash
from server_manager.webservice.util.data_access import DB


def dev_startup(sio_app: socketio.AsyncServer):
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
    sio_app.instrument(
        auth={
            "username": "admin",
            "password": "password",
        }
    )
    sm_logger.info(
        f"Socket.io admin panel enabled at\n{Fore.BLUE}https://admin.socket.io/?username=admin&server=http://%s/socket.io/{Fore.RESET}",
        os.environ.get("SM_API_BACKEND"),
    )
