from fastapi import APIRouter

from server_manager.webservice.db_models import Servers
from server_manager.webservice.util.data_access import DB

server = APIRouter(tags=["server"])


@server.get("/{server_name}", response_model=Servers)
async def get_server_info(server_name: str):
    """Get information about a specific server"""
    return DB().get_server_by_id(server_name)


@server.delete("/{server_name}")
async def delete_server(server_name: str):
    """Delete a specific server"""
    server = DB().get_server_by_id(server_name)
    if server:
        success = DB().delete_server(server)
        return {"success": success}
    return {"success": False, "error": "Server not found"}


@server.post("/")
async def create_server(server: Servers):
    """Create a new server"""
    return DB().create_server(server)
