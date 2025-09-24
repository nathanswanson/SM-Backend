"""
management_api.py

Management API for user authentication and account management

Author: Nathan Swanson
"""

import os
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from server_manager.webservice.db_models import Users
from server_manager.webservice.util.auth import auth_aquire_access_token, auth_get_active_user, create_user

login = APIRouter(tags=["access"])
dev_mode = os.environ.get("SM_ENV") == "DEV"


@login.post("/token")
async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """login user, return access token in cookie"""
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


@login.post("/create")
async def create_user_account(username: str, password: str):
    """create a new user account"""
    return create_user(username, password)


@login.post("/me")
async def get_user(current_user: Annotated[Users, Depends(auth_get_active_user)]):
    """get current user information"""
    return current_user
