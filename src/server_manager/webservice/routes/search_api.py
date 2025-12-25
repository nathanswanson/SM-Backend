from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server_manager.webservice.db_models import Users
from server_manager.webservice.models import (
    NodeListResponse,
    ServerListResponse,
    TemplateListResponse,
    UserListResponse,
)
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.data_access import DB, get_db

router = APIRouter()


@router.get("/users/", response_model=UserListResponse)
def search(current_user: Annotated[Users, Depends(auth_get_active_user)], db: Annotated[DB, Depends(get_db)]):
    """Search for users by username or email"""
    if current_user.admin:
        pass
    return UserListResponse(items={user.username: user.id for user in db.get_users()})


@router.get("/servers/", response_model=ServerListResponse)
def search_servers(current_user: Annotated[Users, Depends(auth_get_active_user)], db: Annotated[DB, Depends(get_db)]):
    """Search for servers by name"""
    if current_user.id is None:
        raise HTTPException(status_code=400, detail="Failed to get current user ID")
    return ServerListResponse(items={server.name: server.id for server in db.get_server_list(current_user.id)})


# @router.get("/fs/{server_id}/{path:path}", response_model=ServerFileListResponse)
# async def search_fs(
#     server_id: int,
#     current_user: Annotated[Users, Depends(auth_get_active_user)],
#     db: Annotated[DB, Depends(get_db)],
#     path: str = "",
# ):
#     """Search for files in a container's filesystem"""
#     server = db.get_server(server_id)
#     if server is None:
#         raise HTTPException(status_code=404, detail="Server not found")
#     ret = await docker_list_directory(server.container_name, path)
#     if ret is None:
#         raise HTTPException(status_code=404, detail="Container not found or path invalid")
#     # remove all non relevant paths
#     template = db.get_template(server.template_id)
#     if template is None:
#         raise HTTPException(status_code=500, detail="Template not found for server: " + server.name)
#     accessible_paths: list[str] = template.exposed_volume or []
#     paths = []
#     for relative_path in ret[0] + [f"{folder}/" for folder in ret[1]]:
#         full_path = os.path.join(path, relative_path)
#         for accessible_path in accessible_paths:
#             if full_path.startswith(accessible_path):
#                 paths.append(relative_path)
#                 break
#     return ServerFileListResponse(items=paths)


@router.get("/nodes/", response_model=NodeListResponse)
def search_nodes(
    current_user: Annotated[Users, Depends(auth_get_active_user)],  # noqa: ARG001
    db: Annotated[DB, Depends(get_db)],
):
    """Search for nodes by name"""

    return NodeListResponse(items={node.name: node.id for node in db.get_nodes()})


@router.get("/templates/", response_model=TemplateListResponse)
def search_templates(current_user: Annotated[Users, Depends(auth_get_active_user)], db: Annotated[DB, Depends(get_db)]):  # noqa: ARG001
    """Search for templates by name"""

    return TemplateListResponse(items={template.name: template.id for template in db.get_templates()})
