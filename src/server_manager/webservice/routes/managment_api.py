"""
management_api.py

Management API for user authentication and account management

Author: Nathan Swanson
"""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from server_manager.webservice.db_models import Users, UsersBase
from server_manager.webservice.models import CreateUserRequest, Token
from server_manager.webservice.util.auth import (
    auth_aquire_access_token,
    auth_get_active_user,
    create_user,
)
from server_manager.webservice.util.data_access import DB

router = APIRouter()
dev_mode = os.environ.get("SM_ENV") == "DEV"


@router.post("/", response_model=UsersBase)
async def create_user_account(create_user_request: CreateUserRequest):
    """create a new user account"""
    return create_user(
        create_user_request.username, create_user_request.password.get_secret_value(), create_user_request.scopes
    )


@router.delete("/", response_model=dict)
async def delete_user_account(
    current_user: Annotated[Users, Security(auth_get_active_user, scopes=["management.delete_user"])],
):
    """delete current user account"""
    # delete user from db
    if current_user.id is None:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    DB().delete_user(current_user.id)
    return {"message": "User deleted successfully"}


@router.post("/token")
async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """login user, return access token"""

    return await auth_aquire_access_token(form_data)


@router.post("/revoke")
async def logout_user(current_user: Annotated[Users, Depends(auth_get_active_user)]):  # noqa: ARG001
    """logout user, delete access token cookie"""
    # return response with message
    # TODO: implement token revocation
    return JSONResponse(content={"message": "Logout successful"})


@router.get("/me", response_model=UsersBase)
async def get_user(current_user: Annotated[Users, Security(auth_get_active_user, scopes=["management.me"])]):
    """get current user information"""
    return current_user
