"""
auth.py

Authentication and user management utilities

Author: Nathan Swanson
"""

import os
from datetime import UTC, datetime, timedelta
from typing import Annotated, Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from server_manager.webservice.db_models import Users
from server_manager.webservice.models import Token, TokenData
from server_manager.webservice.util.data_access import DB

load_dotenv()

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 30
_SECRET_KEY = os.environ["SM_SECRET_KEY"]

_salt = bcrypt.gensalt()


def verify_password(plain_password: str, hashed_password: str):
    """verify a plain password against a hashed password"""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except ValueError:
        return False


def get_password_hash(password: str):
    """hash a password for storing"""
    return bcrypt.hashpw(password.encode(), _salt).decode()


def auth_user(username: str, password: str):
    """authenticate user by username and password, return user if valid"""
    user = DB().get_user_by_username(username)
    if not user:
        return False
    return user if verify_password(password, user.hashed_password) else False


def create_user(username: str, password: str):
    """create a new user with disabled=True by default"""
    user: Users = Users(
        username=username, id=None, disabled=True, admin=False, hashed_password=get_password_hash(password)
    )
    return DB().create_user(user)


def create_access_token(data: dict, expired_delta: timedelta | None = None):
    """create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(UTC) + expired_delta if expired_delta else datetime.now(UTC) + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _SECRET_KEY, algorithm=_ALGORITHM)


async def auth_get_user(
    token_cookie: Optional[str] = Cookie(default=None, alias="token"),
    authorization: Optional[str] = Header(default=None),
):
    """get user from token in cookie or Authorization header"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate User",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = None

    # Prefer cookie
    if token_cookie:
        token = token_cookie
    # Fallback: Authorization: Bearer <token>
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :]

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception  # noqa: TRY301
        token_data = TokenData(username=username)
    except Exception:  # noqa: BLE001
        raise credentials_exception  # noqa: B904

    user = DB().get_user_by_username(token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def auth_get_active_user(current_user: Annotated[Users, Depends(auth_get_user)]):
    """get active user, raise exception if user is disabled"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Disabled account")
    return current_user


async def auth_aquire_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """authenticate user and return access token"""
    user = auth_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expire = timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expired_delta=access_token_expire)
    return Token(access_token=access_token, token_type="bearer", expire_time=access_token_expire.seconds)  # noqa: S106
