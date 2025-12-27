import asyncio
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from threading import Event
from typing import Any, cast, override

from kubernetes import client, config, watch
from kubernetes.client.exceptions import ApiException

from server_manager.webservice.interface.interface import ControllerStreamingInterface
from server_manager.webservice.logger import sm_logger
from server_manager.webservice.models import Metrics

# Default namespace for game servers
CRD_INSTANCES_NAMESPACE = "game-servers"


class KubernetesStreamingAPI(ControllerStreamingInterface):
    """Kubernetes-based streaming for logs and metrics."""

    def __init__(self):
        """Initialize the Kubernetes client configuration."""
        try:
            # Try in-cluster config first (when running inside a pod)
            config.load_incluster_config()
            sm_logger.info("Loaded in-cluster Kubernetes configuration for streaming")
        except config.ConfigException:
            try:
                # Fall back to kubeconfig (local development)
                config.load_kube_config()
                sm_logger.info("Loaded kubeconfig Kubernetes configuration for streaming")
            except config.ConfigException as e:
                sm_logger.error(f"Failed to load Kubernetes configuration: {e}")
                raise

    def _get_core_api(self) -> client.CoreV1Api:
        """Get the CoreV1Api client for pod operations."""
        return client.CoreV1Api()

    def _get_custom_objects_api(self) -> client.CustomObjectsApi:
        """Get the CustomObjectsApi client for metrics."""
        return client.CustomObjectsApi()

    async def _find_pod(self, container_name: str, namespace: str) -> str | None:
        """Find the pod name for a given container/deployment name."""
        try:
            core_api = self._get_core_api()
            loop = asyncio.get_event_loop()
            pods = await loop.run_in_executor(
                None,
                lambda: core_api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"app={container_name}",
                ),
            )
            if pods.items:
                return pods.items[0].metadata.name
            return None
        except ApiException as e:
            sm_logger.error(f"Failed to find pod for {container_name}: {e}")
            return None

    @override
    async def stream_logs(
        self, container_name: str, namespace: str, tail: int = 100, follow: bool = True
    ) -> AsyncGenerator[str, None]:  # type: ignore[override]
        """Stream logs from a Kubernetes pod."""
        ns = namespace
        pod_name = await self._find_pod(container_name, ns)

        if not pod_name:
            sm_logger.error(f"No pod found for {container_name} in namespace {ns}")
            return

        core_api = self._get_core_api()

        try:
            if follow:
                # Use a queue + thread to avoid blocking the event loop
                log_queue: Queue[str | None] = Queue()
                stop_event = Event()

                def watch_logs() -> None:
                    """Run the blocking watch in a separate thread."""
                    w = watch.Watch()
                    try:
                        for line in w.stream(
                            core_api.read_namespaced_pod_log,
                            name=pod_name,
                            namespace=ns,
                            container=container_name,
                            follow=True,
                            tail_lines=tail,
                            _request_timeout=3600,
                        ):
                            if stop_event.is_set():
                                break
                            log_queue.put(str(line) + "\n")
                    except Exception as e:
                        sm_logger.error(f"Watch thread error: {e}")
                    finally:
                        w.stop()
                        log_queue.put(None)  # Signal end of stream

                # Start the watch in a thread
                loop = asyncio.get_event_loop()
                executor = ThreadPoolExecutor(max_workers=1)
                future = loop.run_in_executor(executor, watch_logs)

                try:
                    while True:
                        try:
                            # Non-blocking check with timeout
                            line = await asyncio.wait_for(
                                loop.run_in_executor(None, lambda: log_queue.get(timeout=0.1)),
                                timeout=0.5,
                            )
                            if line is None:  # End of stream
                                break
                            yield line
                        except (Empty, asyncio.TimeoutError):
                            # No data yet, yield control and continue
                            await asyncio.sleep(0.01)
                            continue
                except asyncio.CancelledError:
                    sm_logger.debug(f"Log stream for {container_name} was cancelled")
                    stop_event.set()
                    raise
                finally:
                    stop_event.set()
                    executor.shutdown(wait=False)
            else:
                # Just get historical logs (run in executor to not block)
                loop = asyncio.get_event_loop()
                logs = await loop.run_in_executor(
                    None,
                    lambda: core_api.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=ns,
                        container=container_name,
                        tail_lines=tail,
                    ),
                )
                if logs:
                    yield logs
        except ApiException as e:
            sm_logger.error(f"Failed to stream logs for {container_name}: {e}")

    @override
    async def stream_metrics(self, container_name: str, namespace: str) -> AsyncGenerator[Metrics, None]:  # type: ignore[override]
        """Stream metrics from a Kubernetes pod using metrics-server."""
        ns = namespace
        pod_name = await self._find_pod(container_name, ns)

        if not pod_name:
            sm_logger.error(f"No pod found for {container_name} in namespace {ns}")
            return

        custom_api = self._get_custom_objects_api()
        loop = asyncio.get_event_loop()

        try:
            while True:
                try:
                    # Get pod metrics from metrics-server (run in executor to avoid blocking)
                    metrics_response = await loop.run_in_executor(
                        None,
                        lambda: custom_api.get_namespaced_custom_object(
                            group="metrics.k8s.io",
                            version="v1beta1",
                            namespace=ns,
                            plural="pods",
                            name=pod_name,
                        ),
                    )
                    metrics_dict = cast(dict[str, Any], metrics_response)

                    # Parse metrics from the response
                    containers = metrics_dict.get("containers", [])
                    if containers:
                        # Find the matching container or use first one
                        container_metrics: dict[str, Any] | None = None
                        for c in containers:
                            if isinstance(c, dict) and c.get("name") == container_name:
                                container_metrics = c
                                break
                        if not container_metrics and containers:
                            container_metrics = containers[0] if isinstance(containers[0], dict) else None

                        usage = container_metrics.get("usage", {}) if container_metrics else {}
                        cpu_usage = self._parse_cpu(usage.get("cpu", "0"))
                        memory_usage = self._parse_memory(usage.get("memory", "0"))

                        yield Metrics(
                            cpu=cpu_usage,
                            memory=memory_usage,
                            disk=0.0,  # Not available from metrics-server
                            network=0.0,  # Not available from metrics-server
                        )

                except ApiException as e:
                    if e.status == 404:
                        sm_logger.debug(f"Metrics not yet available for {pod_name}")
                    else:
                        sm_logger.error(f"Failed to get metrics for {container_name}: {e}")
                    # Yield zero metrics on error
                    yield Metrics(cpu=0.0, memory=0.0, disk=0.0, network=0.0)

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            sm_logger.debug(f"Metrics stream for {container_name} was cancelled")
            raise

    def _parse_cpu(self, cpu_str: str) -> float:
        """Parse CPU usage string from metrics-server.

        Examples: '100m' (millicores), '1' (cores), '500n' (nanocores)
        Returns percentage (0-100 scale per core)
        """
        if not cpu_str:
            return 0.0
        try:
            if cpu_str.endswith("n"):
                # Nanocores
                return float(cpu_str[:-1]) / 1_000_000_000 * 100
            elif cpu_str.endswith("m"):
                # Millicores
                return float(cpu_str[:-1]) / 1000 * 100
            else:
                # Cores
                return float(cpu_str) * 100
        except (ValueError, TypeError):
            return 0.0

    def _parse_memory(self, memory_str: str) -> float:
        """Parse memory usage string from metrics-server.

        Examples: '100Ki', '50Mi', '1Gi'
        Returns MB
        """
        if not memory_str:
            return 0.0
        try:
            if memory_str.endswith("Ki"):
                return float(memory_str[:-2]) / 1024
            elif memory_str.endswith("Mi"):
                return float(memory_str[:-2])
            elif memory_str.endswith("Gi"):
                return float(memory_str[:-2]) * 1024
            elif memory_str.endswith("K"):
                return float(memory_str[:-1]) / 1000
            elif memory_str.endswith("M"):
                return float(memory_str[:-1])
            elif memory_str.endswith("G"):
                return float(memory_str[:-1]) * 1000
            else:
                # Bytes
                return float(memory_str) / (1024 * 1024)
        except (ValueError, TypeError):
            return 0.0
