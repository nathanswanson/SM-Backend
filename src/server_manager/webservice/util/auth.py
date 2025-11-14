"""
auth.py

Authentication and user management utilities

Author: Nathan Swanson
"""

import os
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, SecurityScopes

from server_manager.webservice.db_models import Users, UsersCreate
from server_manager.webservice.models import Token, TokenData
from server_manager.webservice.util.data_access import DB

load_dotenv()

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60
_SECRET_KEY = os.environ["SM_SECRET_KEY"]

_salt = bcrypt.gensalt()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/token", scopes={"me": "Read information about the current user"})
oauth2_wrapper: dict = {"dependencies": [Depends(oauth2_scheme)]}


def secure_scope(scope: list[str] | str, dependencies: list | None):
    """
    Create a security dependency configuration with specified scopes and additional dependencies.

    Args:
        scope: A single scope string or list of scope strings required for authorization.
               If empty, uses the default oauth2_wrapper without scope enforcement.
        dependencies: Optional list of additional dependencies to include in the configuration.

    Returns:
        A dictionary containing the dependencies configuration for FastAPI route security.
    """
    if isinstance(scope, str):
        scope = [scope]
    ret: dict[str, list] = (
        {"dependencies": Security(auth_get_active_user, scopes=scope)} if scope else oauth2_wrapper.copy()
    )
    if dependencies:
        ret["dependencies"].extend(dependencies)
    return ret


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
    user = DB().lookup_username(username)
    if not user:
        return False
    return user if verify_password(password, user.hashed_password) else False


def create_user(username: str, password: str, scopes: list[str]):
    """create a new user with disabled=True by default"""
    user: UsersCreate = UsersCreate(username=username, scopes=scopes, disabled=True, admin=False)
    return DB().create_user(user, password=password)


def create_access_token(data: dict, expired_delta: timedelta | None = None):
    """create a JWT access token"""
    to_encode = data.copy()
    expire = (
        datetime.now(UTC) + expired_delta
        if expired_delta
        else datetime.now(UTC) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    to_encode.update({"scopes": data.get("scopes", "me")})

    return jwt.encode(to_encode, _SECRET_KEY, algorithm=_ALGORITHM)


def verify_token(token: str, credentials_exception: HTTPException):
    """verify a JWT token and return the payload"""
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

    except jwt.ExpiredSignatureError as e:
        raise credentials_exception from e
    except jwt.InvalidKeyError as e:
        raise credentials_exception from e
    except jwt.DecodeError as e:
        raise credentials_exception from e

    else:
        return payload


async def auth_get_user(security_scopes: SecurityScopes, token: Annotated[str, Depends(oauth2_scheme)]):
    """get user from token in cookie or Authorization header"""

    authenticate_value = f'Bearer scope="{security_scopes.scope_str}"' if security_scopes.scopes else "Bearer"
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate User",
        headers={"WWW-Authenticate": authenticate_value},
    )
    try:
        payload = verify_token(token, credentials_exception=credentials_exception)
        scope = payload.get("scopes", "")
        print(scope)
        token_scopes = scope.split() if scope else []
        token_data = TokenData(scopes=token_scopes, username=payload.get("sub"))
    except Exception:  # noqa: BLE001
        raise credentials_exception  # noqa: B904

    user = DB().lookup_username(token_data.username)
    if user is None:
        raise credentials_exception
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return user


async def auth_get_active_user(current_user: Annotated[Users, Security(auth_get_user, scopes=["me"])]):
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
    return Token(access_token=access_token, token_type="bearer", expire_time=access_token_expire.seconds)  # noqa: S106, not a password
