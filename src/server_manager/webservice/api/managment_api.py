from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from server_manager.webservice.util.auth import auth_aquire_access_token

login = APIRouter(tags=["access"])


@login.post("/token")
async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    return await auth_aquire_access_token(form_data)
