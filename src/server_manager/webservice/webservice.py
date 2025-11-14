"""
webservice.py

Main webservice app file, includes all routers and socket io handling

Author: Nathan Swanson
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from server_manager.webservice import graphql
from server_manager.webservice.logger import sm_logger
from server_manager.webservice.routes import (
    managment_api,
    nodes_api,
    search_api,
    server_api,
    template_api,
    volumes_api,
)
from server_manager.webservice.util.auth import oauth2_wrapper
from server_manager.webservice.util.dev import dev_startup
from server_manager.webservice.util.env_check import startup_info

# main app
app = FastAPI(root_path="/api")
# CORS middleware
cors_allowed_origins = [
    "https://admin.socket.io",
    "https://vite.localhost",
    f"{'https' if os.environ.get('SM_ENV') != 'DEV' else 'https'}://{os.environ.get('SM_API_BACKEND')}",
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
app.include_router(template_api.router, **oauth2_wrapper, prefix="/templates", tags=["templates"])
app.include_router(managment_api.router, prefix="/users", tags=["users"])
app.include_router(server_api.router, **oauth2_wrapper, prefix="/servers", tags=["servers"])
app.include_router(nodes_api.router, **oauth2_wrapper, prefix="/nodes", tags=["nodes"])
app.include_router(search_api.router, **oauth2_wrapper, prefix="/search", tags=["search"])
app.include_router(volumes_api.router, **oauth2_wrapper, prefix="/volumes", tags=["volumes"])


# graphql
app.include_router(graphql.router, prefix="/graphql", tags=["graphql"])


def generate_operation_id():
    """Generate a unique operation ID"""

    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name


generate_operation_id()
startup_info()
if os.environ.get("SM_ENV") == "DEV":
    dev_startup()
