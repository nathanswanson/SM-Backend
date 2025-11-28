"""
auth.py

Authentication and user management utilities

Author: Nathan Swanson
"""

import os
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Annotated

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, SecurityScopes

from server_manager.webservice.db_models import Users, UsersCreate
from server_manager.webservice.logger import sm_logger
from server_manager.webservice.models import Token, TokenData, TokenPair
from server_manager.webservice.util.data_access import DB

load_dotenv()

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60
_REFRESH_TOKEN_DAYS = 30

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="users/token", scopes={"management.me": "Read information about the current user"}
)
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
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def auth_user(username: str, password: str):
    """authenticate user by username and password, return user if valid"""
    user = DB().lookup_username(username)
    if not user:
        return False
    return user if verify_password(password, user.hashed_password) else False


def create_user(username: str, password: str, scopes: list[str]):
    """create a new user with disabled=True by default"""
    user: UsersCreate = UsersCreate(username=username, scopes=scopes, disabled=True, admin=False)
    return DB().create_user(user, password=get_password_hash(password))


def create_access_token(data: dict, expired_delta: timedelta | None = None):
    """create a JWT access token"""
    to_encode = data.copy()
    expire = (
        datetime.now(UTC) + expired_delta
        if expired_delta
        else datetime.now(UTC) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    to_encode.update({"scopes": data.get("scopes", "")})

    return jwt.encode(to_encode, get_key(), algorithm=_ALGORITHM)


def create_refresh_token(data: dict, expired_delta: timedelta | None = None):
    """create a JWT refresh token"""
    to_encode = data.copy()
    expire = (
        datetime.now(UTC) + expired_delta if expired_delta else datetime.now(UTC) + timedelta(days=_REFRESH_TOKEN_DAYS)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, get_key(), algorithm=_ALGORITHM)


@cache
def get_key():
    """Get the secret key from environment variable."""
    key = os.getenv("SM_SECRET_KEY")
    if key is None:
        msg = "SM_SECRET_KEY environment variable not set"
        sm_logger.critical(msg)
        raise RuntimeError(msg)
    return key


def verify_token(token: str, credentials_exception: HTTPException):
    """verify a JWT token and return the payload"""
    try:
        payload = jwt.decode(token, get_key(), algorithms=[_ALGORITHM])
        username: str = payload.get("sub")
        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp, tz=UTC) < datetime.now(UTC):
            raise credentials_exception
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

    payload = verify_token(token, credentials_exception=credentials_exception)
    exp = payload.get("exp")
    if exp is None or datetime.fromtimestamp(exp, tz=UTC) < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": authenticate_value},
        )
    scope = payload.get("scopes", "")

    token_scopes = scope
    token_data = TokenData(scopes=token_scopes, expires_at=payload.get("exp"), username=payload.get("sub"))

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


async def auth_get_active_user(current_user: Annotated[Users, Security(auth_get_user, scopes=["management.me"])]):
    """get active user, raise exception if user is disabled"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Disabled account")
    return current_user


def create_tokens_for_user(user: Users) -> TokenPair:
    """create access and refresh tokens for a given user"""
    access_token_expire = timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes}, expired_delta=access_token_expire
    )
    refresh_token = create_refresh_token(data={"sub": user.username}, expired_delta=timedelta(days=_REFRESH_TOKEN_DAYS))

    return TokenPair(
        access_token=Token(
            token=access_token,
            token_type="bearer",  # noqa: S106 is not hardcoded secret
            expires_in=access_token_expire.seconds,
        ),
        refresh_token=Token(
            token=refresh_token,
            token_type="bearer",  # noqa: S106 is not hardcoded secret
            expires_in=_REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        ),
    )


async def auth_renew_token(refresh_token: str):
    """return a new access/refresh token using a existing refresh token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = verify_token(refresh_token, credentials_exception=credentials_exception)
        username: str = payload.get("sub")

    except Exception:  # noqa: BLE001
        raise credentials_exception  # noqa: B904

    user = DB().lookup_username(username)
    if user is None:
        raise credentials_exception

    return create_tokens_for_user(user)


async def auth_aquire_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenPair:
    """authenticate user and return access token"""
    user = auth_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return create_tokens_for_user(user)
