import asyncio
from enum import StrEnum

import socketio

from server_manager.webservice.docker_interface.docker_container_api import docker_container_name_exists, merge_streams


def socketio_app(origins: list[str]) -> socketio.AsyncServer:
    # socket io reroute
    sio_app = socketio.AsyncServer(
        logger=False,
        engineio_logger=False,
        async_mode="asgi",
        cors_allowed_origins=origins,
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
    return sio_app
