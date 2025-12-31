from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server_manager.webservice.db_models import ServersCreate, ServersRead, Users

# from server_manager.webservice.interface.docker_api.server_router import ServerRouter
from server_manager.webservice.interface.interface_manager import ControllerContainerInterface, get_container_client
from server_manager.webservice.models import (
    ContainerCommandResponse,
    ServerDeleteResponse,
    ServerStartResponse,
    ServerStatusResponse,
    ServerStopResponse,
)
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.logger import sm_logger
router = APIRouter()


@router.post("/", response_model=ServersRead)
async def create_server(
    server: ServersCreate,
    current_user: Annotated[Users, Depends(auth_get_active_user)],
    client: Annotated[ControllerContainerInterface, Depends(get_container_client)],
):
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
    if not current_user.id:
        raise HTTPException(status_code=400, detail="Invalid user")
    await client.create(server, template, tenant_id=current_user.id)
    return DB().create_server(server, port=template.exposed_port, linked_users=[current_user])


@router.get("/{server_id}", response_model=ServersRead)
async def get_server_info(server_id: int):
    """Get information about a specific server"""
    server = DB().get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    return server


@router.delete("/{server_id}", response_model=ServerDeleteResponse)
async def delete_server(server_id: int, client: Annotated[ControllerContainerInterface, Depends(get_container_client)]):
    """Delete a specific server"""
    server = DB().get_server(server_id)
    if server and server.container_name:
        await client.remove(server.container_name, namespace="game-servers")
    success = DB().delete_server(server_id)
    if success:
        return {"success": success}
    return {"success": False, "error": "Server not found"}


@router.post("/{server_id}/start", response_model=ServerStartResponse)
async def start_server(server_id: int, client: Annotated[ControllerContainerInterface, Depends(get_container_client)]):
    """Start a specific server"""
    # get container name from servers(name)
    server = DB().get_server(server_id)
    if not server:
        return {"success": False, "error": "Server not found"}
    ret = await client.start(server.container_name, namespace="game-servers")

    return {"success": ret}


@router.post("/{server_id}/stop", response_model=ServerStopResponse)
async def stop_server(server_id: int, client: Annotated[ControllerContainerInterface, Depends(get_container_client)]):
    """Stop a specific server"""

    server = DB().get_server(server_id)
    if not server:
        return {"success": False, "error": "Server not found"}

    ret = await client.stop(server.container_name, namespace="game-servers")
    return {"success": ret}


@router.get("/{server_id}/status", response_model=ServerStatusResponse | None)
async def get_server_status(
    server_id: int, client: Annotated[ControllerContainerInterface, Depends(get_container_client)]
):
    """Get the running status of a specific server"""
    server = DB().get_server(server_id)
    if not server:
        return {"running": False}
    is_running = await client.is_running(server.container_name, namespace="game-servers")
    health = (
        await client.health_status(server.container_name, namespace="game-servers")
        if is_running
        else None
    )
    return ServerStatusResponse(running=is_running, health=health)


@router.post("/{server_id}/command", response_model=ContainerCommandResponse)
async def send_command(
    server_id: int, command: str, client: Annotated[ControllerContainerInterface, Depends(get_container_client)]
):
    server = DB().get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    sm_logger.debug(f"Sending command to server {server_id}: {command}, id: {server.linked_users[0].id}")
    
    ret = await client.command(server.container_name, command, namespace=f"tenant-{server.linked_users[0].id}")
    return ContainerCommandResponse(success=ret)
