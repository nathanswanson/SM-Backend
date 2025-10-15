"""
container_api.py

API endpoints for managing Docker containers and their associated volumes.

Author: Nathan Swanson

"""

from fastapi import APIRouter

from server_manager.webservice.docker_interface.docker_container_api import (
    docker_container_logs_tail,
    docker_container_send_command,
)
from server_manager.webservice.models import (
    ContainerCommandResponse,
    ContainerLogsResponse,
)

router = APIRouter()
metric_data_rate = 10


@router.get("/{container_name}/logs", response_model=ContainerLogsResponse)
async def get_log_message(container_name: str, line_count: int | None = None) -> ContainerLogsResponse:
    """get the last line_count lines of container logs, defaults to 25 if not specified"""
    ret = await docker_container_logs_tail(container_name, tail=line_count or 25)
    return ContainerLogsResponse(items=ret if ret else [])


@router.get("/{container_name}/command", response_model=ContainerCommandResponse)
async def send_command(container_name: str, command: str):
    """send a command to a container"""
    ret = await docker_container_send_command(container_name, command)
    return ContainerCommandResponse(success=ret)
