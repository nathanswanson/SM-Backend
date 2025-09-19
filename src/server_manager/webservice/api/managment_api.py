import os
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from server_manager.webservice.db_models import User
from server_manager.webservice.util.auth import auth_aquire_access_token, auth_get_active_user

login = APIRouter(tags=["access"])
dev_mode = os.environ.get("SM_ENV") == "DEV"


@login.post("/token")
async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    token = await auth_aquire_access_token(form_data)
    response = JSONResponse(content={"message": "Login successful"})
    response.set_cookie(
        key="token",
        value=token.access_token,
        httponly=True,
        secure=not dev_mode,
        samesite="lax" if dev_mode else "strict",
        max_age=token.expire_time,
    )
    return response


@login.post("/me")
async def get_user(current_user: Annotated[User, Depends(auth_get_active_user)]):
    return current_user
