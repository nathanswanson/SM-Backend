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
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles

from server_manager.webservice.api.container_api import container
from server_manager.webservice.api.managment_api import login
from server_manager.webservice.api.nodes_api import system
from server_manager.webservice.api.template_api import template
from server_manager.webservice.docker_interface.docker_container_api import (
    docker_container_name_exists,
    merge_streams,
)
from server_manager.webservice.util.auth import auth_get_active_user

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
)

if os.environ.get("SM_ENV") == "DEV":
    logging.getLogger().setLevel(logging.DEBUG)
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
if os.environ.get("SM_ENV") == "DEV":
    logging.info("CORS middleware enabled")
    cors_allowed_origins = ["http://localhost:4000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

oauth2_wrapper: dict = {}

# if os.environ.get("SM_ENV") != "DEV":
oauth2_wrapper = {"dependencies": [Depends(auth_get_active_user)]}

app.include_router(container, **oauth2_wrapper)
app.include_router(template, **oauth2_wrapper)
app.include_router(system, **oauth2_wrapper)
# if os.environ.get("SM_ENV") != "DEV":
app.include_router(login)

# frontend
app.mount("/", StaticFiles(directory=STATIC_PATH, html=True), name="static")


# socket io reroute
sio_app = socketio.AsyncServer(
    logger=False, engineio_logger=False, async_mode="asgi", cors_allowed_origins=cors_allowed_origins
)
app = socketio.ASGIApp(sio_app, app)


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
        await asyncio.sleep(1)


sio_app.start_background_task(process_all_rooms_task)
