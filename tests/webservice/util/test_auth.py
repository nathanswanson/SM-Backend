# filepath: /home/wsl/Textual/server-manager/builder/SM-Backend/src/server_manager/webservice/util/test_auth.py
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from starlette import status

from server_manager.webservice.db_models import UsersRead
from server_manager.webservice.util.auth import (
    _ALGORITHM,
    _SECRET_KEY,
    auth_user,
    create_access_token,
    create_user,
    get_password_hash,
    verify_password,
    verify_token,
)


def test_password_hashing_and_verification():
    """
    Tests that password hashing and verification work correctly.
    """
    password = "testpassword"
    hashed_password = get_password_hash(password)
    assert hashed_password != password
    assert verify_password(password, hashed_password)
    assert not verify_password("wrongpassword", hashed_password)


def test_create_access_token():
    """
    Tests the creation of a JWT access token.
    """
    data = {"sub": "testuser"}
    token = create_access_token(data)
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
    # 1. Create a mock DB instance that will be returned by DB()
    mock_db_instance = mocker.MagicMock()
    mock_user = mocker.MagicMock()
    mock_user.hashed_password = get_password_hash("correctpassword")
    mock_db_instance.lookup_username.return_value = mock_user

    # 2. Patch the DB class in the 'auth' module.
    #    When DB() is called, it will now return our mock_db_instance instead.
    monkeypatch.setattr("server_manager.webservice.util.auth.DB", lambda: mock_db_instance)

    # 3. Run the test - this now calls the mock object's method
    result = auth_user("testuser", "correctpassword")

    # 4. Assertions
    assert result == mock_user
    mock_db_instance.lookup_username.assert_called_once_with("testuser")


def test_auth_user_not_found(mocker, monkeypatch):
    """
    Tests that auth_user returns False when the user is not found.
    """
    # 1. Create a mock DB instance that will be returned by DB()
    mock_db_instance = mocker.MagicMock()
    mock_db_instance.lookup_username.return_value = None

    # 2. Patch the DB class in the 'auth' module.
    #    When DB() is called, it will now return our mock_db_instance instead.
    monkeypatch.setattr("server_manager.webservice.util.auth.DB", lambda: mock_db_instance)

    # 3. Run the test - this now calls the mock object's method
    result = auth_user("nonexistentuser", "somepassword")

    # 4. Assertions
    assert result is False
    mock_db_instance.lookup_username.assert_called_once_with("nonexistentuser")


def test_user_disabled_by_default(mocker, monkeypatch):
    """
    Tests that a newly created user is disabled by default without DB calls.
    """
    # 1. Create a mock DB instance that will be returned by DB()
    mock_db_instance = mocker.MagicMock()

    # 2. Configure the mock's create_user method to simulate the real one
    def mock_create_user_func(user, password):  # noqa: ARG001 mock function must match signature
        return UsersRead(id=1, **user.model_dump())

    mock_db_instance.create_user.side_effect = mock_create_user_func

    # 3. Patch the DB class in the 'auth' module.
    #    When DB() is called, it will now return our mock_db_instance instead.
    monkeypatch.setattr("server_manager.webservice.util.auth.DB", lambda: mock_db_instance)

    # 4. Run the test - this now calls the mock object's method
    username = "newuser"
    password = "newpassword"
    scopes = ["read", "write"]
    user = create_user(username, password, scopes)

    # 5. Assertions remain the same
    assert user.username == username
    assert user.disabled is True
    assert user.admin is False

    # 6. Verify that the mock method was called
    mock_db_instance.create_user.assert_called_once()


def test_create_access_token_with_expiry():
    """
    Tests the creation of a JWT access token with a specific expiry time.
    """
    data = {"sub": "testuser"}
    expires_delta = timedelta(minutes=30)
    token = create_access_token(data, expired_delta=expires_delta)
    decoded_token = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    expire = decoded_token["exp"]
    expected_expire = datetime.now(UTC) + expires_delta
    # Allow a small grace period for execution time
    assert abs(datetime.fromtimestamp(expire, tz=UTC) - expected_expire) < timedelta(seconds=5)


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
    # Create a token that expired 1 second ago
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
    # handle bad key
    monkeypatch.setattr("server_manager.webservice.util.auth._SECRET_KEY", "")
    with pytest.raises(HTTPException) as excinfo:
        verify_token(token, credentials_exception=credentials_exception)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
