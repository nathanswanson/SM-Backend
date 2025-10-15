"""
webservice.py

Main webservice app file, includes all routers and socket io handling

Author: Nathan Swanson
"""

import os
from pathlib import Path

import socketio
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from server_manager.webservice.logger import sm_logger
from server_manager.webservice.routes import managment_api, nodes_api, search_api, server_api, template_api
from server_manager.webservice.routes.containers import api, volumes_api
from server_manager.webservice.socket import socketio_app
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.dev import dev_startup
from server_manager.webservice.util.env_check import startup_info

# main app
fastapi_app = FastAPI()
# CORS middleware
cors_allowed_origins = [
    "https://admin.socket.io",
    f"{'https' if os.environ.get('SM_ENV') != 'DEV' else 'http'}://{os.environ.get('SM_API_BACKEND')}",
]
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
sm_logger.debug("CORS allowed origins: %s", cors_allowed_origins)
# routers
oauth2_wrapper: dict = {"dependencies": [Depends(auth_get_active_user)]}
api.router.include_router(volumes_api.router)
fastapi_app.include_router(api.router, **oauth2_wrapper, prefix="/container", tags=["container"])
fastapi_app.include_router(template_api.router, **oauth2_wrapper, prefix="/template", tags=["template"])
fastapi_app.include_router(managment_api.router, prefix="/system", tags=["system"])
fastapi_app.include_router(server_api.router, **oauth2_wrapper, prefix="/server", tags=["server"])
fastapi_app.include_router(nodes_api.router, **oauth2_wrapper, prefix="/nodes", tags=["nodes"])
fastapi_app.include_router(search_api.router, **oauth2_wrapper, prefix="/search", tags=["search"])
# frontend


STATIC_PATH = os.environ.get("SM_STATIC_PATH", "NULL")

if Path(STATIC_PATH) != Path("NULL"):
    fastapi_app.mount("/", StaticFiles(directory=STATIC_PATH, html=True), name="static")
fastapi_app.add_middleware(GZipMiddleware, minimum_size=1000)


def generate_operation_id():
    """Generate a unique operation ID"""

    for route in fastapi_app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name


generate_operation_id()
startup_info()
sio_app = socketio_app(origins=cors_allowed_origins)
app = socketio.ASGIApp(sio_app, other_asgi_app=fastapi_app)
if os.environ.get("SM_ENV") == "DEV":
    dev_startup(sio_app)
