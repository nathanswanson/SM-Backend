import asyncio
from collections.abc import AsyncGenerator
from typing import Any, override

import aiodocker

from server_manager.webservice.interface.interface import ControllerStreamingInterface
from server_manager.webservice.logger import sm_logger
from server_manager.webservice.models import Metrics


def _try_get(obj: Any, *keys: str | int) -> int:
    """Safely navigate nested dicts/lists and return an int value."""
    if not isinstance(obj, dict):
        return 0
    head = obj
    for key in keys:
        new_head = head[key] if isinstance(key, int) else head.get(key)
        if new_head is None:
            return 0
        head = new_head
    return int(head) if isinstance(head, (str, int)) else 0


class DockerStreamingAPI(ControllerStreamingInterface):
    """Docker-based streaming for logs and metrics using aiodocker."""

    @override
    async def stream_logs(
        self, container_name: str, namespace: str, tail: int = 100, follow: bool = True
    ) -> AsyncGenerator[str, None]:  # type: ignore[override]
        """Stream logs from a Docker container.

        Note: namespace parameter is ignored for Docker (kept for interface compatibility).
        """
        try:
            async with aiodocker.Docker() as client:
                container = await client.containers.get(container_name)

                if follow:
                    # Stream logs continuously
                    async for line in container.log(stdout=True, stderr=True, follow=True, tail=tail):
                        yield line
                        await asyncio.sleep(0)
                else:
                    # Get historical logs
                    logs = await container.log(stdout=True, stderr=True, tail=tail)
                    if logs:
                        yield "".join(logs)

        except aiodocker.exceptions.DockerError as e:
            sm_logger.error(f"Failed to stream logs for {container_name}: {e}")
        except asyncio.CancelledError:
            sm_logger.debug(f"Log stream for {container_name} was cancelled")
            raise

    @override
    async def stream_metrics(self, container_name: str, namespace: str) -> AsyncGenerator[Metrics, None]:  # type: ignore[override]
        """Stream metrics from a Docker container.

        Note: namespace parameter is ignored for Docker (kept for interface compatibility).
        """
        if not container_name:
            sm_logger.debug("No container name provided for stats streaming.")
            return

        try:
            async with aiodocker.Docker() as client:
                container = await client.containers.get(container_name)

                async for stat in container.stats():
                    used_memory = _try_get(stat, "memory_stats", "usage") or 0
                    available_memory = _try_get(stat, "memory_stats", "limit") or 0
                    memory_usage_perc = (
                        round(used_memory / available_memory * 100, 2) if available_memory > 0 else 0.0
                    )

                    cpu_delta = _try_get(stat, "cpu_stats", "cpu_usage", "total_usage") - _try_get(
                        stat, "precpu_stats", "cpu_usage", "total_usage"
                    )
                    system_delta = _try_get(stat, "cpu_stats", "system_cpu_usage") - _try_get(
                        stat, "precpu_stats", "system_cpu_usage"
                    )
                    online_cpus = _try_get(stat, "cpu_stats", "online_cpus")
                    cpu_usage_perc = (
                        round((cpu_delta / system_delta) * online_cpus * 100, 2)
                        if system_delta > 0 and cpu_delta > 0
                        else 0.0
                    )

                    blk_io_read = _try_get(stat, "blkio_stats", "io_service_bytes_recursive", 0, "value")
                    blk_io_write = _try_get(stat, "blkio_stats", "io_service_bytes_recursive", 1, "value")

                    yield Metrics(
                        cpu=cpu_usage_perc,
                        memory=memory_usage_perc,
                        disk=float(blk_io_read),
                        network=float(blk_io_write),
                    )
                    await asyncio.sleep(1)

        except aiodocker.exceptions.DockerError as e:
            sm_logger.error(f"Failed to stream metrics for {container_name}: {e}")
        except asyncio.CancelledError:
            sm_logger.debug(f"Metrics stream for {container_name} was cancelled")
            raise
