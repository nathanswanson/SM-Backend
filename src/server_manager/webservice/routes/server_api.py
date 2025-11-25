from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server_manager.webservice.db_models import ServersCreate, ServersRead, Users
from server_manager.webservice.interface.docker.docker_container_api import (
    docker_container_create,
    docker_container_health_status,
    docker_container_remove,
    docker_container_running,
    docker_container_send_command,
    docker_container_start,
    docker_container_stop,
)
from server_manager.webservice.models import (
    ContainerCommandResponse,
    ServerDeleteResponse,
    ServerStartResponse,
    ServerStatusResponse,
    ServerStopResponse,
)
from server_manager.webservice.net.server_router import ServerRouter
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.data_access import DB

router = APIRouter()


@router.post("/", response_model=ServersRead)
async def create_server(server: ServersCreate, current_user: Annotated[Users, Depends(auth_get_active_user)]):
    """Create a new server"""
    # create container of Servers.name name
    # start with template then override with server data if present
    template = DB().get_template(server.template_id)
    server.container_name = server.name
    # make sure server doesn't already exist
    existing_server = DB().get_server_by_name(server.name)
    if existing_server:
        raise HTTPException(status_code=400, detail="Server with that name already exists")
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    docker_ret = await docker_container_create(server.name, template.image, server.env, server_link=server.name)
    if not docker_ret:
        raise HTTPException(status_code=500, detail="Failed to create Docker container")
    return DB().create_server(server, port=DB().unused_port(len(template.exposed_port)), linked_users=[current_user])


@router.get("/{server_id}", response_model=ServersRead)
async def get_server_info(server_id: int):
    """Get information about a specific server"""
    server = DB().get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    return server


@router.delete("/{server_id}", response_model=ServerDeleteResponse)
async def delete_server(server_id: int):
    """Delete a specific server"""
    server = DB().get_server(server_id)
    if server and server.container_name:
        await docker_container_remove(server.container_name)
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
    ret = await docker_container_start(server.container_name)
    if ret:
        await ServerRouter().open_ports(server)
    return {"success": ret}


@router.post("/{server_id}/stop", response_model=ServerStopResponse)
async def stop_server(server_id: int):
    """Stop a specific server"""
    server = DB().get_server(server_id)
    if not server:
        return {"success": False, "error": "Server not found"}
    ret = await docker_container_stop(server.container_name)
    if ret:
        ServerRouter().close_ports(server)
    return {"success": ret}


@router.get("/{server_id}/status", response_model=ServerStatusResponse | None)
async def get_server_status(server_id: int):
    """Get the running status of a specific server"""
    server = DB().get_server(server_id)
    if not server:
        return {"running": False}
    is_running = await docker_container_running(server.container_name)
    health = await docker_container_health_status(server.container_name) if is_running else None
    return ServerStatusResponse(running=is_running, health=health)


@router.post("/{server_id}/command", response_model=ContainerCommandResponse)
async def send_command(server_id: int, command: str):
    server = DB().get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    ret = await docker_container_send_command(server.container_name, command)
    return ContainerCommandResponse(success=ret)
