"""
management_api.py

Management API for user authentication and account management

Author: Nathan Swanson
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from server_manager.webservice.db_models import Users, UsersBase
from server_manager.webservice.models import CreateUserRequest
from server_manager.webservice.util.auth import (
    auth_aquire_token,
    auth_get_active_user,
    auth_renew_token,
    create_user,
)
from server_manager.webservice.util.data_access import DB, get_db

router = APIRouter()


@router.post("/", response_model=UsersBase)
async def create_user_account(create_user_request: CreateUserRequest):
    """create a new user account"""
    return create_user(
        create_user_request.username, create_user_request.password.get_secret_value(), create_user_request.scopes
    )


@router.delete("/", response_model=dict)
async def delete_user_account(
    current_user: Annotated[Users, Security(auth_get_active_user, scopes=["management.delete_user"])],
    db: Annotated[DB, Depends(get_db)],
):
    """delete current user account"""
    # delete user from db
    assert current_user.id is not None
    db.delete_user(current_user.id)
    return {"message": "User deleted successfully"}


@router.post("/refresh")
async def refresh_token(request: Request):
    """refresh access token using refresh token"""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    new_tokens = await auth_renew_token(refresh_token)  # set new access token in cookie
    response = JSONResponse({"access_token": new_tokens.access_token.token})
    response.set_cookie(
        key="refresh_token",
        value=new_tokens.refresh_token.token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=2592000,
        # path="/",
    )
    return response


@router.post("/token")
async def login_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """login user, return access token and set refresh token to cookie"""
    tokens = await auth_aquire_token(form_data)
    response = JSONResponse({"access_token": tokens.access_token.token})
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token.token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=2592000,
        # path="/",
    )
    return response


@router.post("/revoke")
async def logout_user(current_user: Annotated[Users, Depends(auth_get_active_user)]):  # noqa: ARG001
    """logout user, delete access token cookie"""
    # return response with message
    # TODO: implement token revocation
    response = JSONResponse({"message": "Logout successful"})
    response.set_cookie("refresh_token", "", max_age=0)
    response.delete_cookie("refresh_token")
    return response


@router.get("/me", response_model=UsersBase)
async def get_user(current_user: Annotated[Users, Security(auth_get_active_user, scopes=["management.me"])]):
    """get current user information"""
    return current_user
