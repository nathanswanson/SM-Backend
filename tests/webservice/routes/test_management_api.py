"""
test_management_api.py

Tests for the management API

Author: Nathan Swanson
"""

from server_manager.webservice.db_models import Users
from server_manager.webservice.models import Token
from server_manager.webservice.util.auth import auth_get_active_user
from server_manager.webservice.util.data_access import get_db


def test_create_user_account(mocker, test_client):
    """Test creating a user account"""
    mock_user = Users(id=1, username="testuser", scopes=["management.me"], hashed_password="password")
    mocker.patch("server_manager.webservice.routes.management_api.create_user", return_value=mock_user)

    response = test_client.post(
        "/users/",
        json={"username": "testuser", "password": "password", "scopes": ["management.me"]},
    )

    assert response.status_code == 200
    assert response.json() == {"username": "testuser", "disabled": True, "scopes": ["management.me"], "admin": False}


def test_delete_user_account(test_client, mock_db):
    """Test deleting a user account"""
    mock_user = Users(id=1, username="testuser", scopes=["management.delete_user"], hashed_password="password")
    # Mock the dependency injection
    test_client.app.dependency_overrides[auth_get_active_user] = lambda: mock_user
    test_client.app.dependency_overrides[get_db] = lambda: mock_db

    response = test_client.delete(
        "/users/",
        headers={"Authorization": "Bearer testtoken"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "User deleted successfully"}
    mock_db.delete_user.assert_called_once_with(1)

    # Clean up dependency override
    test_client.app.dependency_overrides = {}


def test_login_user(mocker, test_client):
    """Test logging in a user"""
    mock_token = Token(access_token="testtoken", token_type="bearer")

    mocker.patch("server_manager.webservice.routes.management_api.auth_aquire_access_token", return_value=mock_token)

    response = test_client.post(
        "/users/token",
        data={"username": "testuser", "password": "password"},
    )

    assert response.status_code == 200
    assert response.json() == {"access_token": "testtoken", "token_type": "bearer", "expire_time": None}


def test_logout_user(test_client):
    """Test logging out a user"""
    mock_user = Users(id=1, username="testuser", scopes=["management.me"], hashed_password="password")

    # Mock the dependency injection
    test_client.app.dependency_overrides[auth_get_active_user] = lambda: mock_user

    response = test_client.post(
        "/users/revoke",
        headers={"Authorization": "Bearer testtoken"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Logout successful"}

    # Clean up dependency override
    test_client.app.dependency_overrides = {}


def test_get_user(test_client):
    """Test getting user information"""
    mock_user = Users(id=1, username="testuser", scopes=["management.me"], hashed_password="password")

    # Mock the dependency injection
    test_client.app.dependency_overrides[auth_get_active_user] = lambda: mock_user

    response = test_client.get(
        "/users/me",
        headers={"Authorization": "Bearer testtoken"},
    )

    assert response.status_code == 200
    assert response.json() == {"username": "testuser", "disabled": True, "scopes": ["management.me"], "admin": False}

    # Clean up dependency override
    test_client.app.dependency_overrides = {}
