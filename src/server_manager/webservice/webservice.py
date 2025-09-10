import logging
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer

from server_manager.webservice.api.container_api import container
from server_manager.webservice.api.managment_api import login
from server_manager.webservice.api.system_api import system
from server_manager.webservice.api.template_api import template
from server_manager.webservice.api.websocket_api import ws


def web_server_start(host: str, port: int, dev: bool):
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
    log_path = Path(__file__).resolve().parent.parent / "logs"
    Path(log_path).mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
    )

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4000", "http://raspberrypi.home:4000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    oauth2_wrapper: dict = {}
    if not dev:
        oauth2_wrapper = {"dependencies": [Depends(oauth2_scheme)]}
    app.include_router(container, **oauth2_wrapper)
    app.include_router(template, **oauth2_wrapper)
    app.include_router(system, **oauth2_wrapper)
    app.include_router(ws, **oauth2_wrapper)
    if not dev:
        app.include_router(login)

    uvicorn.run(app, host=host, port=port)
