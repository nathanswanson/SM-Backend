from unittest.mock import AsyncMock, MagicMock

import aiodocker
import fastapi
import pytest
from pytest_mock import MockerFixture

from server_manager.webservice.util.context_provider import docker_container


@pytest.fixture
def mock_docker_client(mocker: MockerFixture) -> MagicMock:
    """Fixture to mock the docker_client context manager."""
    mock_client = mocker.patch("server_manager.webservice.util.context_provider.docker_client")
    mock_client_instance = mock_client.return_value.__aenter__.return_value

    # Mock the container proxy object that will be returned by containers.get()
    mock_container_proxy = AsyncMock()
    mock_container_proxy.show.return_value = {"Name": "mock-container"}
    mock_client_instance.containers.get.return_value = mock_container_proxy

    return mock_client_instance


@pytest.mark.asyncio
async def test_docker_container_success(mock_docker_client: MagicMock):
    """Test the success path of the docker_container context manager."""
    # Act
    async with docker_container("mock-container") as container:
        # Assert
        assert container is not None
        container_info = await container.show()
        assert container_info["Name"] == "mock-container"
        container.show.assert_awaited_once()  # type: ignore
        mock_docker_client.containers.get.assert_awaited_once_with("mock-container")


@pytest.mark.asyncio
async def test_docker_container_failure_not_found(mock_docker_client: MagicMock):
    """Test the failure path when a container is not found."""
    # Arrange
    mock_docker_client.containers.get.side_effect = aiodocker.exceptions.DockerError(
        status=404, data={"message": "No such container"}
    )
    container_ret = "unmodified"
    # Act
    # make sure it raises the HTTPException
    with pytest.raises(fastapi.exceptions.HTTPException):
        async with docker_container("non-existent-container") as container:
            # Assert
            container_ret = container
    assert container_ret == "unmodified"
    mock_docker_client.containers.get.assert_awaited_once_with("non-existent-container")
