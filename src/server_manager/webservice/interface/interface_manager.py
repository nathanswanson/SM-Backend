import importlib.util
import logging
import os
from collections.abc import Generator
from typing import Any, cast

from server_manager.webservice.interface.interface import ControllerContainerInterface

log = logging.getLogger(__name__)


def get_container_client():
    if importlib.util.find_spec("kubernetes") and os.environ.get("SM_K8S"):
        log.info("Using KubernetesContainerAPI")

        kubernetes_api_module = importlib.import_module(
            "server_manager.webservice.interface.kubernetes_api.container_api"
        )
        return kubernetes_api_module.KubernetesContainerAPI()

    if importlib.util.find_spec("aiodocker"):
        log.info("Using DockerContainerAPI")

        docker_api_module = importlib.import_module("server_manager.webservice.interface.docker_api.container_api")
        return docker_api_module.DockerContainerAPI()

    msg = (
        "No supported container backend available. Install the 'kubernetes' extra "
        "(pip install -e '.[kubernetes]') or 'aiodocker'."
    )
    raise ImportError(msg)


def get_volume_client():
    if importlib.util.find_spec("kubernetes") and os.environ.get("SM_K8S"):
        log.info("Using KubernetesVolumeAPI")

        kubernetes_api_module = importlib.import_module("server_manager.webservice.interface.kubernetes_api.volume_api")
        return kubernetes_api_module.KubernetesVolumeAPI()

    if importlib.util.find_spec("aiodocker"):
        log.info("Using DockerVolumeAPI")

        docker_api_module = importlib.import_module("server_manager.webservice.interface.docker_api.volume_api")
        return docker_api_module.DockerVolumeAPI()

    msg = (
        "No supported container backend available. Install the 'kubernetes' extra "
        "(pip install -e '.[kubernetes]') or 'aiodocker'."
    )
    raise ImportError(msg)


def get_interface_manager() -> Generator[ControllerContainerInterface, Any, None]:
    client = get_container_client()
    try:
        yield cast(ControllerContainerInterface, client)
    finally:
        pass
