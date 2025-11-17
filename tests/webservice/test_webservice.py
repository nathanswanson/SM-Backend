from fastapi import FastAPI


def test_app_creation(app_instance: FastAPI):
    """
    Tests that the main FastAPI app is created successfully.
    """
    assert app_instance is not None
    assert isinstance(app_instance, FastAPI)
