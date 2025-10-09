from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server_manager.webservice.db_models import Users
from server_manager.webservice.docker_interface.docker_container_api import docker_container_running
from server_manager.webservice.docker_interface.docker_volume_api import docker_list_directory
from server_manager.webservice.models import (
    ContainerFileListResponse,
    NodeListResponse,
    ServerListResponse,
    TemplateListResponse,
    UserListResponse,
)
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.data_access import DB

router = APIRouter()


@router.get("/users/", response_model=UserListResponse)
def search(current_user: Annotated[Users, Depends(auth_get_active_user)]):
    """Search for users by username or email"""
    if current_user.admin:
        pass
    return UserListResponse(items={user.username: user.id for user in DB().get_users()})


@router.get("/servers/", response_model=ServerListResponse)
def search_servers(current_user: Annotated[Users, Depends(auth_get_active_user)]):
    """Search for servers by name"""
    return ServerListResponse(items={server.name: server.id for server in DB().get_server_list(current_user)})


@router.get("/fs/{container_name}/{path:path}", response_model=ContainerFileListResponse)
async def search_fs(container_name: str, current_user: Annotated[Users, Depends(auth_get_active_user)], path: str = ""):  # noqa: ARG001
    """Search for files in a container's filesystem"""

    if not await docker_container_running(container_name):
        raise HTTPException(status_code=400, detail="Container is not running")
    ret = await docker_list_directory(container_name, path)
    if ret is None:
        raise HTTPException(status_code=404, detail="Container not found or path invalid")

    return ContainerFileListResponse(items=ret if ret else [])


@router.get("/nodes/", response_model=NodeListResponse)
def search_nodes(current_user: Annotated[Users, Depends(auth_get_active_user)]):  # noqa: ARG001
    """Search for nodes by name"""

    return NodeListResponse(items={node.name: node.id for node in DB().get_nodes()})


@router.get("/templates/", response_model=TemplateListResponse)
def search_templates(current_user: Annotated[Users, Depends(auth_get_active_user)]):  # noqa: ARG001
    """Search for templates by name"""

    return TemplateListResponse(items={template.name: template.id for template in DB().get_templates()})
