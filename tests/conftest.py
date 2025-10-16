"""
conftest.py

Global fixtures for pytest
"""

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def set_test_env_vars():
    """
    Fixture to set environment variables for the entire test session.
    """
    print("\n--- Loading test environment variables ---")
    os.environ["SM_ENV"] = "TEST"
    # Use an in-memory SQLite database for tests for simplicity.
    # For tests involving postgres-specific features, you'd point this to a test Postgres DB.
    os.environ["SM_DB_URL"] = "sqlite:///:memory:"
    os.environ["SM_STATIC_PATH"] = "/tmp/static"  # Dummy path for tests
    os.environ["SM_API_BACKEND"] = "localhost"
