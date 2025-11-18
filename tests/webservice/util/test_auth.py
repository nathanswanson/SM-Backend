from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import jwt
import pytest
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, SecurityScopes

from server_manager.webservice.db_models import Users, UsersRead
from server_manager.webservice.util.auth import (
    _ALGORITHM,
    _SECRET_KEY,
    auth_aquire_access_token,
    auth_get_active_user,
    auth_get_user,
    auth_user,
    create_access_token,
    create_user,
    get_password_hash,
    secure_scope,
    verify_password,
    verify_token,
)


@pytest.fixture
def setup_secret_key(monkeypatch):
    monkeypatch.setenv("SM_SECRET_KEY", "testsecretkey")


def test_password_hashing_and_verification():
    """
    Tests that password hashing and verification work correctly.
    """
    password = "testpassword"
    hashed_password = get_password_hash(password)
    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("wrongpassword", hashed_password)


@pytest.mark.usefixtures("setup_secret_key")
def test_create_access_token():
    """
    Tests the creation of a JWT access token.
    """
    data = {"sub": "testuser"}
    token = create_access_token(data)
    assert _SECRET_KEY is not None
    decoded_token = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    assert decoded_token["sub"] == "testuser"
    assert "exp" in decoded_token


def test_verify_password_invalid_hash():
    """
    Tests that verify_password returns False for an invalid hashed password.
    """
    password = "testpassword"
    invalid_hashed_password = "invalidhash"
    assert not verify_password(password, invalid_hashed_password)


def test_auth_user_success(mocker, monkeypatch):
    """
    Tests that auth_user returns the user when authentication is successful.
    """

    mock_db_instance = mocker.MagicMock()
    mock_user = mocker.MagicMock()
    mock_user.hashed_password = get_password_hash("correctpassword")
    mock_db_instance.lookup_username.return_value = mock_user

    monkeypatch.setattr("server_manager.webservice.util.auth.DB", lambda: mock_db_instance)

    result = auth_user("testuser", "correctpassword")

    assert result == mock_user
    mock_db_instance.lookup_username.assert_called_once_with("testuser")


def test_auth_user_not_found(mocker, monkeypatch):
    """
    Tests that auth_user returns False when the user is not found.
    """
    mock_db_instance = mocker.MagicMock()
    mock_db_instance.lookup_username.return_value = None

    monkeypatch.setattr("server_manager.webservice.util.auth.DB", lambda: mock_db_instance)

    result = auth_user("nonexistentuser", "somepassword")

    assert result is False
    mock_db_instance.lookup_username.assert_called_once_with("nonexistentuser")


def test_user_disabled_by_default(mocker, monkeypatch):
    """
    Tests that a newly created user is disabled by default without DB calls.
    """

    mock_db_instance = mocker.MagicMock()

    def mock_create_user_func(user, password):
        return UsersRead(id=1, **user.model_dump())

    mock_db_instance.create_user.side_effect = mock_create_user_func

    monkeypatch.setattr("server_manager.webservice.util.auth.DB", lambda: mock_db_instance)

    username = "newuser"
    password = "newpassword"
    scopes = ["read", "write"]
    user = create_user(username, password, scopes)

    assert user.username == username
    assert user.disabled is True
    assert user.admin is False

    mock_db_instance.create_user.assert_called_once()


@pytest.mark.usefixtures("setup_secret_key")
def test_create_access_token_with_expiry():
    """
    Tests the creation of a JWT access token with a specific expiry time.
    """
    data = {"sub": "testuser"}
    expires_delta = timedelta(minutes=30)
    token = create_access_token(data, expired_delta=expires_delta)
    assert _SECRET_KEY is not None
    decoded_token = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    expire = decoded_token["exp"]
    expected_expire = datetime.now(UTC) + expires_delta

    assert abs(datetime.fromtimestamp(expire, tz=UTC) - expected_expire) < timedelta(seconds=5)


@pytest.mark.usefixtures("setup_secret_key")
def test_verify_token_valid():
    """
    Tests that a valid token is verified correctly.
    """
    username = "testuser"
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = create_access_token(data={"sub": username})
    payload = verify_token(token, credentials_exception=credentials_exception)
    assert payload.get("sub") == username


def test_verify_token_expired():
    """
    Tests that an expired token raises an HTTPException.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = create_access_token(data={"sub": "testuser"}, expired_delta=timedelta(seconds=-1))
    with pytest.raises(HTTPException) as excinfo:
        verify_token(token, credentials_exception=credentials_exception)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_verify_token_invalid(monkeypatch):
    """
    Tests that an invalid token raises an HTTPException.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = "thisisnotavalidtoken"
    with pytest.raises(HTTPException) as excinfo:
        verify_token(token, credentials_exception=credentials_exception)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED

    monkeypatch.setattr("server_manager.webservice.util.auth._SECRET_KEY", "")
    with pytest.raises(HTTPException) as excinfo:
        verify_token(token, credentials_exception=credentials_exception)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_secure_scope_with_and_without_scopes():
    result = secure_scope("management.me", dependencies=None)
    assert "dependencies" in result

    extra = object()
    scoped = secure_scope([], dependencies=[extra])
    assert scoped["dependencies"][-1] is extra


@pytest.mark.asyncio
async def test_auth_get_user_success(monkeypatch, mocker):
    user = UsersRead(id=1, username="user", scopes=["management.me"], disabled=False, admin=False)
    mock_db = mocker.MagicMock()
    mock_db.lookup_username.return_value = user
    monkeypatch.setattr("server_manager.webservice.util.auth.DB", lambda: mock_db)
    monkeypatch.setattr(
        "server_manager.webservice.util.auth.verify_token",
        lambda token, credentials_exception: {"sub": "user", "scopes": ["management.me"]},
    )

    result = await auth_get_user(SecurityScopes(scopes=["management.me"]), token="token")

    assert result is user


@pytest.mark.asyncio
async def test_auth_get_user_missing_scope(monkeypatch, mocker):
    user = UsersRead(id=1, username="user", scopes=["basic"], disabled=False, admin=False)
    mock_db = mocker.MagicMock()
    mock_db.lookup_username.return_value = user
    monkeypatch.setattr("server_manager.webservice.util.auth.DB", lambda: mock_db)
    monkeypatch.setattr(
        "server_manager.webservice.util.auth.verify_token",
        lambda token, credentials_exception: {"sub": "user", "scopes": ["basic"]},
    )

    with pytest.raises(HTTPException) as exc:
        await auth_get_user(SecurityScopes(scopes=["management.me"]), token="token")

    assert exc.value.detail == "Not enough permissions"


@pytest.mark.asyncio
async def test_auth_get_user_missing_user(monkeypatch, mocker):
    mock_db = mocker.MagicMock()
    mock_db.lookup_username.return_value = None
    monkeypatch.setattr("server_manager.webservice.util.auth.DB", lambda: mock_db)
    monkeypatch.setattr(
        "server_manager.webservice.util.auth.verify_token",
        lambda token, credentials_exception: {"sub": "ghost", "scopes": []},
    )

    with pytest.raises(HTTPException):
        await auth_get_user(SecurityScopes(scopes=[]), token="token")


@pytest.mark.asyncio
async def test_auth_get_active_user_rejects_disabled():
    user = UsersRead(id=1, username="user", scopes=[], disabled=True, admin=False)

    with pytest.raises(HTTPException):
        await auth_get_active_user(cast(Users, user))


@pytest.mark.asyncio
async def test_auth_aquire_access_token_success(monkeypatch):
    user = SimpleNamespace(username="user", scopes=["scope"], disabled=False)
    monkeypatch.setattr("server_manager.webservice.util.auth.auth_user", lambda u, p: user)

    form = OAuth2PasswordRequestForm(username="user", password="pw", scope="")
    token = await auth_aquire_access_token(form)

    assert token.token_type == "bearer"
    assert token.access_token


@pytest.mark.asyncio
async def test_auth_aquire_access_token_invalid(monkeypatch):
    monkeypatch.setattr("server_manager.webservice.util.auth.auth_user", lambda u, p: False)

    form = OAuth2PasswordRequestForm(username="user", password="pw", scope="")
    with pytest.raises(HTTPException):
        await auth_aquire_access_token(form)
