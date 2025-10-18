"""
container_api.py

API endpoints for managing Docker containers and their associated volumes.

Author: Nathan Swanson

"""

from fastapi import APIRouter, HTTPException

from server_manager.webservice.docker_interface.docker_container_api import (
    docker_container_logs_tail,
    docker_container_send_command,
)
from server_manager.webservice.models import (
    ContainerCommandResponse,
    ContainerLogsResponse,
)
from server_manager.webservice.util.data_access import DB

router = APIRouter()
metric_data_rate = 10


@router.get("/{server_id}/logs", response_model=ContainerLogsResponse)
async def get_log_message(server_id: int, line_count: int | None = None) -> ContainerLogsResponse:
    """get the last line_count lines of container logs, defaults to 25 if not specified"""
    server = DB().get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    ret = await docker_container_logs_tail(server.container_name, tail=line_count or 25)
    return ContainerLogsResponse(items=ret if ret else [])


@router.post("/{server_id}/command", response_model=ContainerCommandResponse)
async def send_command(server_id: int, command: str):
    server = DB().get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    ret = await docker_container_send_command(server.container_name, command)
    return ContainerCommandResponse(success=ret)
