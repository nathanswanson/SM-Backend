import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import strawberry
from strawberry.fastapi import GraphQLRouter
from strawberry.subscriptions import GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL

from server_manager.webservice.logger import sm_logger
from server_manager.webservice.models import Metrics
from server_manager.webservice.util.context_provider import docker_container


@strawberry.experimental.pydantic.type(model=Metrics, all_fields=True)
class MetricsQL:
    pass


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def get_metrics(self, container_name: str) -> AsyncGenerator[MetricsQL, None]:
        if not container_name:
            return
        try:
            async for metric in stats(container_name):
                yield metric
        except TimeoutError:
            sm_logger.debug(f"Metrics subscription for container {container_name} timed out.")
        except asyncio.CancelledError:
            sm_logger.debug(f"Metrics subscription for container {container_name} was cancelled.")

    @strawberry.subscription
    async def get_logs(self, container_name: str) -> AsyncGenerator[str, None]:
        async with docker_container(container_name) as container:
            if not container:
                return

            # Get the last 100 lines and yield as a single payload
            historical_logs = await container.log(stdout=True, stderr=True, tail=100)
            if historical_logs:
                yield "".join(historical_logs)

            # Stream new logs line by line
            try:
                async for line in container.log(stdout=True, stderr=True, follow=True, tail=1):
                    yield line
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                # This is expected when the client disconnects.
                # The context manager will handle closing the connection.
                pass


@strawberry.type
class Query:
    @strawberry.field
    async def get_metrics(self) -> str:
        return "not used"


schema = strawberry.Schema(query=Query, subscription=Subscription)
router = GraphQLRouter(
    schema,
    graphql_ide="graphiql",
    allow_queries_via_get=True,
    subscription_protocols=[GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL],
)


def try_get(obj: Any, *keys: str | int) -> int:
    if not (isinstance(obj, (dict))):
        return 0
    head = obj
    for key in keys:
        new_head = head[key] if isinstance(key, int) else head.get(key)
        if new_head is None:
            return 0
        head = new_head
    return int(head) if isinstance(head, (str, int)) else 0


async def stats(container_name: str) -> AsyncGenerator[MetricsQL, None]:
    """
    Stream metrics from a container. `Notes`_
    """
    if not container_name:
        sm_logger.debug("No container name provided for stats streaming.")
        return
    async with docker_container(container_name) as container:
        if container:
            async for stat in container.stats():
                used_memory = try_get(stat, "memory_stats", "usage") or 0
                available_memory = try_get(stat, "memory_stats", "limit") or 0
                memory_usage_perc = round(used_memory / available_memory * 100, 2) if available_memory > 0 else 0.0
                cpu_delta = try_get(stat, "cpu_stats", "cpu_usage", "total_usage") - try_get(
                    stat, "precpu_stats", "cpu_usage", "total_usage"
                )
                system_delta = try_get(stat, "cpu_stats", "system_cpu_usage") - try_get(
                    stat, "precpu_stats", "system_cpu_usage"
                )
                online_cpus = try_get(stat, "cpu_stats", "online_cpus")
                cpu_usage_perc = (
                    round((cpu_delta / system_delta) * online_cpus * 100, 2)
                    if system_delta > 0 and cpu_delta > 0
                    else 0.0
                )
                blk_io_read = try_get(stat, "blkio_stats", "io_service_bytes_recursive", 0, "value")
                blk_io_write = try_get(stat, "blkio_stats", "io_service_bytes_recursive", 1, "value")
                yield MetricsQL(cpu=cpu_usage_perc, memory=memory_usage_perc, disk=blk_io_read, network=blk_io_write)
                await asyncio.sleep(1)
