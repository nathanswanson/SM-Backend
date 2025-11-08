"""
management_api.py

Management API for user authentication and account management

Author: Nathan Swanson
"""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from server_manager.webservice.db_models import Users, UsersBase
from server_manager.webservice.models import CreateUserRequest, Token
from server_manager.webservice.util.auth import auth_aquire_access_token, auth_get_active_user, create_user

router = APIRouter()
dev_mode = os.environ.get("SM_ENV") == "DEV"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/token")
oauth2_wrapper: dict = {"dependencies": [Depends(oauth2_scheme)]}


@router.post("/", response_model=UsersBase)
async def create_user_account(create_user_request: CreateUserRequest):
    """create a new user account"""
    return create_user(create_user_request.username, create_user_request.password.get_secret_value())


@router.post("/token")
async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """login user, return access token"""

    return await auth_aquire_access_token(form_data)


@router.post("/revoke", dependencies=[Depends(auth_get_active_user)])
async def logout_user(response: Response, _current_user: Annotated[Users, Depends(auth_get_active_user)]):
    """logout user, delete access token cookie"""
    response.delete_cookie(key="token", httponly=True, secure=not dev_mode, samesite="lax" if dev_mode else "strict")
    # return response with message
    return JSONResponse(headers=response.headers, content={"message": "Logout successful"})


@router.get("/me", response_model=UsersBase)
async def get_user(current_user: Annotated[Users, Depends(auth_get_active_user)]):
    """get current user information"""
    return current_user
