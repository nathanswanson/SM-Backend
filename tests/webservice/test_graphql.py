from typing import TYPE_CHECKING

import pytest

from server_manager.webservice import graphql

if TYPE_CHECKING:
    from strawberry.experimental.pydantic.conversion_types import StrawberryTypeFromPydantic

    from server_manager.webservice.models import Metrics


def test_try_get_returns_nested_value_and_zero_on_invalid():
    payload = {"memory": {"usage": "25"}, "list": [0, {"value": 10}]}

    assert graphql.try_get(payload, "memory", "usage") == 25
    assert graphql.try_get(payload, "list", 1, "value") == 10
    assert graphql.try_get(payload, "missing") == 0
    assert graphql.try_get("not-a-dict", "anything") == 0


@pytest.mark.asyncio
async def test_stats_emits_metrics_for_container(mocker):
    stat = {
        "memory_stats": {"usage": 50, "limit": 100},
        "cpu_stats": {
            "cpu_usage": {"total_usage": 200},
            "system_cpu_usage": 400,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 100},
            "system_cpu_usage": 300,
        },
        "blkio_stats": {
            "io_service_bytes_recursive": [
                {"value": 5},
                {"value": 7},
            ]
        },
    }

    async def stat_stream():
        yield stat

    container = mocker.MagicMock()
    container.stats.return_value = stat_stream()

    docker_cm = mocker.AsyncMock()
    docker_cm.__aenter__.return_value = container
    docker_cm.__aexit__.return_value = False
    mocker.patch("server_manager.webservice.graphql.docker_container", return_value=docker_cm)
    mocker.patch("server_manager.webservice.graphql.asyncio.sleep", new_callable=mocker.AsyncMock)

    gen = graphql.stats("mc")
    metric: StrawberryTypeFromPydantic[Metrics] = await anext(gen)
    assert hasattr(metric, "cpu")
    assert hasattr(metric, "memory")
    assert hasattr(metric, "disk")
    assert hasattr(metric, "network")
    metric_cast: Metrics = metric  # type: ignore
    assert metric_cast.cpu == 200.0
    assert metric_cast.memory == 50.0
    assert metric_cast.disk == 5
    assert metric_cast.network == 7
    with pytest.raises(StopAsyncIteration):
        await anext(gen)


@pytest.mark.asyncio
async def test_stats_short_circuits_without_container_name(mocker):
    debug = mocker.patch("server_manager.webservice.graphql.sm_logger.debug")
    docker_patch = mocker.patch("server_manager.webservice.graphql.docker_container")

    gen = graphql.stats("")
    with pytest.raises(StopAsyncIteration):
        await anext(gen)

    debug.assert_called_once()
    docker_patch.assert_not_called()


@pytest.mark.asyncio
async def test_stats_no_container_found_yields_nothing(mocker):
    docker_cm = mocker.AsyncMock()
    docker_cm.__aenter__.return_value = None
    docker_cm.__aexit__.return_value = False
    mocker.patch("server_manager.webservice.graphql.docker_container", return_value=docker_cm)

    gen = graphql.stats("mc")
    with pytest.raises(StopAsyncIteration):
        await anext(gen)
