import asyncio
import importlib.util
import logging
import os
from collections.abc import Generator
from typing import Any, cast

from server_manager.webservice.db_models import ServersCreate
from server_manager.webservice.interface.interface import ControllerContainerInterface
from server_manager.webservice.routes.template_api import TemplatesCreate

log = logging.getLogger(__name__)


def get_client():
    if importlib.util.find_spec("kubernetes") and os.environ.get("SM_K8S"):
        kubernetes_api_module = importlib.import_module(
            "server_manager.webservice.interface.kubernetes_api.container_api"
        )
        log.debug("Using KubernetesContainerAPI")
        return kubernetes_api_module.KubernetesContainerAPI()

    if importlib.util.find_spec("aiodocker"):
        docker_api_module = importlib.import_module("server_manager.webservice.interface.docker_api.container_api")
        log.debug("Using DockerContainerAPI")
        return docker_api_module.DockerContainerAPI()

    msg = (
        "No supported container backend available. Install the 'kubernetes' extra "
        "(pip install -e '.[kubernetes]') or 'aiodocker'."
    )
    raise ImportError(msg)


def get_interface_manager() -> Generator[ControllerContainerInterface, Any, None]:
    client = get_client()
    try:
        yield cast(ControllerContainerInterface, client)
    finally:
        pass


if __name__ == "__main__":
    # simple test to verify dynamic loading works
    async def test():
        os.environ["SM_ENV"] = "DEV"
        os.environ["SM_K8S"] = "1"  # force k8s for test
        client: ControllerContainerInterface = get_client()
        print(f"Loaded client: {client.__class__.__name__}")
        await client.remove("test-server3")
        # print(asyncio.run(client.create("test-server3", 1, 2, 16, "itzg/minecraft-server", 30001, True, {"EULA": "TRUE"})))
        print(
            client.create(
                ServersCreate(
                    name="test-server3",
                    env={"EULA": "TRUE"},
                    memory=2,
                    cpu=2,
                    disk=1,
                    node_id=1,
                    template_id=1,
                ),
                TemplatesCreate(
                    name="minecraft",
                    image="itzg/minecraft-server",
                    exposed_port=[30001],
                    description="",
                    resource_min_cpu=1,
                    resource_min_mem=1,
                    resource_min_disk=1,
                    modules=[],
                    exposed_volume=["/data"],
                    tags=["latest"],
                ),
            )
        )

    asyncio.run(test())
