"""
webservice.py

Main webservice app file, includes all routers and socket io handling

Author: Nathan Swanson
"""

import asyncio
import logging
import os
import sys
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import socketio
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.routing import APIRoute
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles

from server_manager.webservice.db_models import UsersBase
from server_manager.webservice.docker_interface.docker_container_api import (
    docker_container_name_exists,
    merge_streams,
)
from server_manager.webservice.routes import managment_api, nodes_api, search_api, server_api, template_api
from server_manager.webservice.routes.containers import api, volumes_api
from server_manager.webservice.util.auth import auth_get_active_user, get_password_hash
from server_manager.webservice.util.data_access import DB

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
)

if os.environ.get("SM_ENV") == "DEV":
    logging.debug("Debug logging enabled")

try:
    STATIC_PATH = os.environ["SM_STATIC_PATH"]
except KeyError as e:
    logging.critical("Env var %s is missing. Is the .env missing?", e.args)
    sys.exit(1)
else:
    logging.info("frontend server files path: %s", STATIC_PATH)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
log_path = Path(__file__).resolve().parent.parent / "logs"
Path(log_path).mkdir(parents=True, exist_ok=True)

# main app - gets overridden by socket io app at end of file
app = FastAPI()

# CORS middleware for local dev
cors_allowed_origins = []
logging.info("CORS middleware enabled")
cors_allowed_origins += ["http://localhost:4000", "https://admin.socket.io", f"https://{os.environ.get("SM_API_BACKEND")}"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logging.info("CORS allowed origins: %s", cors_allowed_origins)
oauth2_wrapper: dict = {}
oauth2_wrapper = {"dependencies": [Depends(auth_get_active_user)]}
api.router.include_router(volumes_api.router)
app.include_router(api.router, **oauth2_wrapper, prefix="/container", tags=["container"])

app.include_router(template_api.router, **oauth2_wrapper, prefix="/template", tags=["template"])
app.include_router(managment_api.router, prefix="/system", tags=["system"])
app.include_router(server_api.router, **oauth2_wrapper, prefix="/server", tags=["server"])
app.include_router(nodes_api.router, **oauth2_wrapper, prefix="/nodes", tags=["nodes"])
app.include_router(search_api.router, **oauth2_wrapper, prefix="/search", tags=["search"])
# frontend
if Path(STATIC_PATH) != Path("NULL"):
    app.mount("/app", StaticFiles(directory=STATIC_PATH, html=True), name="static")
app.add_middleware(GZipMiddleware, minimum_size=1000)


def generate_operation_id():
    """Generate a unique operation ID"""

    # TODO: fix type error
    for route in app.routes:  # type: ignore
        if isinstance(route, APIRoute):
            route.operation_id = route.name


generate_operation_id()

# socket io reroute
sio_app = socketio.AsyncServer(
    logger=False,
    engineio_logger=False,
    async_mode="asgi",
    cors_allowed_origins=cors_allowed_origins,
)
app = socketio.ASGIApp(sio_app, app)
sio_app.instrument(
    auth={
        "username": "admin",
        "password": "password",
    }
)


def check_empty_room(room: str):
    empty = True
    for _ in sio_app.manager.get_participants(namespace="/", room=room):
        empty = False
        break

    return empty


class CommandType(StrEnum):
    RECEIVE_NODE = "update_node"
    RECEIVE_CONTAINER = "update_container"
    SEND_LOGS = "push_log"
    SEND_METRICS = "push_metric"


@dataclass
class SessionProvider:
    container_name: str
    node_name: str


type SessionHandler = Callable[[str, SessionProvider], AsyncGenerator[tuple[str, str]]]


@dataclass
class Provider:
    key: str
    session_hander: SessionHandler


@sio_app.event
async def subscribe(sid, data):
    # make sure valid request
    node, container = data.split("+")
    if await docker_container_name_exists(container) is None:
        return  # TODO: add failure response
    await unsubscribe(sid, "")  # leave all prior rooms first
    await sio_app.enter_room(sid, f"{node}+{container}")


@sio_app.event
async def unsubscribe(sid, _data):
    session_rooms = sio_app.rooms(sid)
    if session_rooms == 0:
        return
    for room in session_rooms:
        await sio_app.leave_room(sid, room)


async def process_all_rooms_task():
    while True:
        async for message in await merge_streams():
            await sio_app.emit(event=message.event_type, room=message.room, data=message.data, namespace="/")
            await asyncio.sleep(0)
        await asyncio.sleep(0)


sio_app.start_background_task(process_all_rooms_task)


# create a dev admin
if os.environ.get("SM_ENV") == "DEV" and not DB().get_user_by_username("admin"):
    # create dev data

    DB().create_user(
        UsersBase(
            username="admin",
            disabled=False,
            admin=True,
            hashed_password=get_password_hash("admin"),
        )
    )
    # # dev.sql
    # file_path = files("server_manager").joinpath("resources").joinpath("dev.sql")
    # sql_text = file_path.read_text()

#     DB().exec_raw(sql_text)
