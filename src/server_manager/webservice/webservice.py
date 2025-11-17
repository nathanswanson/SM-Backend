"""
webservice.py

Main webservice app file, includes all routers and socket io handling

Author: Nathan Swanson
"""

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server_manager.webservice import graphql
from server_manager.webservice.logger import sm_logger
from server_manager.webservice.routes import (
    management_api,
    nodes_api,
    search_api,
    server_api,
    template_api,
    volumes_api,
)
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.dev import dev_startup
from server_manager.webservice.util.env_check import generate_operation_id, startup_info

# main app
app = FastAPI(root_path="/api")
# CORS middleware
cors_allowed_origins = [
    "https://admin.socket.io",
    "https://vite.localhost",
    f"https://{os.environ.get('SM_API_BACKEND')}",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
sm_logger.debug("CORS allowed origins: %s", cors_allowed_origins)
# routers
app.include_router(
    template_api.router, dependencies=[Depends(auth_get_active_user)], prefix="/templates", tags=["templates"]
)
app.include_router(management_api.router, prefix="/users", tags=["users"])
app.include_router(server_api.router, dependencies=[Depends(auth_get_active_user)], prefix="/servers", tags=["servers"])
app.include_router(nodes_api.router, dependencies=[Depends(auth_get_active_user)], prefix="/nodes", tags=["nodes"])
app.include_router(search_api.router, dependencies=[Depends(auth_get_active_user)], prefix="/search", tags=["search"])
app.include_router(
    volumes_api.router, dependencies=[Depends(auth_get_active_user)], prefix="/volumes", tags=["volumes"]
)


# graphql
app.include_router(graphql.router, prefix="/graphql", tags=["graphql"])


generate_operation_id(app)
startup_info()
dev_startup()
