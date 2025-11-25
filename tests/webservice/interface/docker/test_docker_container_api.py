from types import SimpleNamespace

import aiodocker
import pytest
from fastapi import HTTPException

from server_manager.webservice.interface.docker import docker_container_api as api


@pytest.fixture
def async_cm_factory(mocker):
    """Create an async context manager that yields the provided object."""

    def _factory(result):
        cm = mocker.AsyncMock()
        cm.__aenter__.return_value = result
        cm.__aexit__.return_value = False
        return cm

    return _factory


@pytest.mark.asyncio
async def test_banned_container_access_raises_forbidden():
    with pytest.raises(HTTPException) as exc:
        await api.docker_container_name_exists("server-manager")

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_container_name_exists_returns_true(mocker, async_cm_factory):
    container = mocker.MagicMock()
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container",
        return_value=async_cm_factory(container),
    )

    assert await api.docker_container_name_exists("mc-server") is True


@pytest.mark.asyncio
async def test_container_stop_invokes_stop(mocker, async_cm_factory):
    container = mocker.AsyncMock()
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container",
        return_value=async_cm_factory(container),
    )

    assert await api.docker_container_stop("mc-server") is True
    container.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_container_stop_returns_false_when_missing(mocker, async_cm_factory):
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container",
        return_value=async_cm_factory(None),
    )

    assert await api.docker_container_stop("ghost") is False


@pytest.mark.asyncio
async def test_container_remove_stops_when_running(mocker, async_cm_factory):
    container = mocker.AsyncMock()
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container",
        return_value=async_cm_factory(container),
    )
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container_running",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )
    stop_mock = mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container_stop",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )

    assert await api.docker_container_remove("mc") is True
    stop_mock.assert_awaited_once()
    container.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_container_start_returns_false_when_missing(mocker, async_cm_factory):
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container",
        return_value=async_cm_factory(None),
    )

    assert await api.docker_container_start("ghost") is False


@pytest.mark.asyncio
async def test_docker_container_running_reads_state(mocker, async_cm_factory):
    container = mocker.AsyncMock()
    container.show.return_value = {"State": {"Running": True}}
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container",
        return_value=async_cm_factory(container),
    )

    assert await api.docker_container_running("mc") is True


@pytest.mark.asyncio
async def test_docker_list_containers_filters_banned(mocker, async_cm_factory):
    allowed = SimpleNamespace(_container={"Names": ["/mc"]})
    banned = SimpleNamespace(_container={"Names": ["/postgres"]})
    client = mocker.MagicMock()
    client.containers.list = mocker.AsyncMock(return_value=[allowed, banned])
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_client",
        return_value=async_cm_factory(client),
    )

    assert await api.docker_list_containers_names() == ["mc"]


@pytest.mark.asyncio
async def test_map_image_volumes_returns_mapped_paths(mocker, monkeypatch):
    monkeypatch.setenv("SM_MOUNT_PATH", "/tmp/mount")
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_get_image_exposed_volumes",
        new_callable=mocker.AsyncMock,
        return_value=["/data", "/config"],
    )

    paths = await api.map_image_volumes("image", "srv1")

    assert paths == ["/tmp/mount/srv1/data:/data", "/tmp/mount/srv1/config:/config"]


@pytest.mark.asyncio
async def test_map_image_volumes_returns_empty_when_none(mocker):
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_get_image_exposed_volumes",
        new_callable=mocker.AsyncMock,
        return_value=None,
    )

    assert await api.map_image_volumes("image", "srv1") == []


def test_get_servers_network_name_reads_subprocess(mocker):
    result = SimpleNamespace(stdout="test_servers\n")
    mocker.patch("server_manager.webservice.interface.docker.docker_container_api.subprocess.run", return_value=result)

    assert api._get_servers_network_name() == "test_servers"


@pytest.mark.asyncio
async def test_container_create_builds_config(mocker, async_cm_factory):
    client = mocker.MagicMock()
    client.containers.create = mocker.AsyncMock()
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_client",
        return_value=async_cm_factory(client),
    )
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.map_image_volumes",
        new_callable=mocker.AsyncMock,
        return_value=["/tmp/mc:/data"],
    )
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api._get_servers_network_name",
        return_value="server_manager_servers",
    )
    mocker.patch("os.makedirs")
    mocker.patch("os.access", return_value=True)

    result = await api.docker_container_create(
        container_name="mc",
        image_name="mc:latest",
        env={"ENV": "prod"},
        server_link="srv",
        user_link="user",
    )

    assert result is True
    client.containers.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_container_create_returns_false_when_volume_not_writable(mocker, async_cm_factory):
    client = mocker.MagicMock()
    client.containers.create = mocker.AsyncMock()
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_client",
        return_value=async_cm_factory(client),
    )
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.map_image_volumes",
        new_callable=mocker.AsyncMock,
        return_value=["/tmp/mc:/data"],
    )
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api._get_servers_network_name",
        return_value="net",
    )
    mocker.patch("os.makedirs")
    mocker.patch("os.access", return_value=False)

    result = await api.docker_container_create(
        container_name="mc",
        image_name="mc:latest",
        env=None,
    )

    assert result is False
    client.containers.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_container_create_handles_docker_error(mocker, async_cm_factory):
    client = mocker.MagicMock()
    client.containers.create = mocker.AsyncMock(side_effect=aiodocker.exceptions.DockerError(500, {"message": "boom"}))
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_client",
        return_value=async_cm_factory(client),
    )
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.map_image_volumes",
        new_callable=mocker.AsyncMock,
        return_value=["/tmp/mc:/data"],
    )
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api._get_servers_network_name",
        return_value="net",
    )
    mocker.patch("os.makedirs")
    mocker.patch("os.access", return_value=True)

    result = await api.docker_container_create(
        container_name="mc",
        image_name="mc:latest",
        env=None,
    )

    assert result is False


@pytest.mark.asyncio
async def test_container_health_status_returns_output(mocker):
    health_info = api.HealthInfo(Start="s", End="e", ExitCode=0, Output="healthy")
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container_inspect",
        new_callable=mocker.AsyncMock,
        return_value=health_info,
    )

    status = await api.docker_container_health_status("mc")

    assert status == "healthy"


@pytest.mark.asyncio
async def test_container_inspect_returns_data(mocker, async_cm_factory):
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container_running",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )
    container = mocker.AsyncMock()
    container.show.return_value = {
        "State": {
            "Health": {
                "Log": [
                    {"Start": "s", "End": "e", "ExitCode": 0, "Output": "ok"},
                    {"Start": "s2", "End": "e2", "ExitCode": 1, "Output": "bad"},
                ]
            }
        }
    }
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container",
        return_value=async_cm_factory(container),
    )

    result = await api.docker_container_inspect("mc")

    assert isinstance(result, api.HealthInfo)
    assert result.output == "bad"


@pytest.mark.asyncio
async def test_container_inspect_raises_when_not_running(mocker):
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container_running",
        new_callable=mocker.AsyncMock,
        return_value=False,
    )

    with pytest.raises(HTTPException) as exc:
        await api.docker_container_inspect("mc")

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_container_inspect_returns_none_without_health(mocker, async_cm_factory):
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container_running",
        new_callable=mocker.AsyncMock,
        return_value=True,
    )
    container = mocker.AsyncMock()
    container.show.return_value = {"State": {"Health": {"Log": []}}}
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container",
        return_value=async_cm_factory(container),
    )

    assert await api.docker_container_inspect("mc") is None


@pytest.mark.asyncio
async def test_container_send_command_attaches_socket(mocker, async_cm_factory):
    sock = mocker.AsyncMock()
    container = mocker.AsyncMock()
    container.attach.return_value = sock
    mocker.patch(
        "server_manager.webservice.interface.docker.docker_container_api.docker_container",
        return_value=async_cm_factory(container),
    )

    assert await api.docker_container_send_command("mc", "say hi") is True
    sock.write_in.assert_awaited_once()
