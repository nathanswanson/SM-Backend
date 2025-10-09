from typing import Annotated

from fastapi import APIRouter, Depends

from server_manager.webservice.db_models import ServersBase, ServersRead, Users
from server_manager.webservice.docker_interface.docker_container_api import (
    docker_container_create,
    docker_container_start,
    docker_container_stop,
)
from server_manager.webservice.models import (
    ServerDeleteResponse,
    ServerStartResponse,
    ServerStatusResponse,
    ServerStopResponse,
)
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.data_access import DB

router = APIRouter()


@router.post("/", response_model=ServersRead)
async def create_server(
    server: ServersBase, template_id: int, node_id: int, current_user: Annotated[Users, Depends(auth_get_active_user)]
):
    """Create a new server"""
    # create container of Servers.name name
    # start with template then override with server data if present
    template = DB().get_template(template_id)
    if template:
        await docker_container_create(server.name, template.image, server.port, server.env)
        return DB().create_server(server, template_id, node_id, owner_id=current_user.id)
    return {"success": False, "error": "Template not found"}


@router.get("/{server_id}", response_model=ServersRead)
async def get_server_info(server_id: int | str):
    """Get information about a specific server"""
    return DB().get_server(server_id)


@router.delete("/{server_id}", response_model=ServerDeleteResponse)
async def delete_server(server_id: int):
    """Delete a specific server"""

    success = DB().delete_server(server_id)
    if success:
        return {"success": success}
    return {"success": False, "error": "Server not found"}


@router.post("/{server_id}/start", response_model=ServerStartResponse)
async def start_server(server_id: int):
    """Start a specific server"""
    # get container name from servers(name)
    server = DB().get_server(server_id)
    if not server:
        return {"success": False, "error": "Server not found"}
    return {"success": await docker_container_start(server.container_name)}


@router.post("/{server_id}/stop", response_model=ServerStopResponse)
async def stop_server(server_id: int):
    """Stop a specific server"""
    server = DB().get_server(server_id)
    if not server:
        return {"success": False, "error": "Server not found"}
    return {"success": await docker_container_stop(server.container_name)}


@router.get("/{server_id}/status", response_model=ServerStatusResponse)
async def get_server_status(server_id: int):
    """Get the running status of a specific server"""
    server = DB().get_server(server_id)
    if not server:
        return {"running": False}
    is_running = await docker_container_start(server.container_name)
    return {"running": is_running}
