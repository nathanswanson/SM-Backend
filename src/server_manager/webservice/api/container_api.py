import asyncio
from math import trunc
from typing import Any, Optional

from docker.models.containers import Container
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from server_manager.webservice.docker_interface.docker_container_api import (
    docker_container_create,
    docker_container_get,
    docker_container_logs,
    docker_container_running,
    docker_list_containers_names,
)
from server_manager.webservice.models import ContainerListResponse, RunningResponse, SuccessResponse
from server_manager.webservice.template_loader import get_template
from server_manager.webservice.util.util import expand_api_url

container = APIRouter(tags=["container"])
metric_data_rate = 10


@container.get(expand_api_url("list"), response_model=ContainerListResponse)
def list_containers():
    return ContainerListResponse(container=docker_list_containers_names())


@container.get(expand_api_url("{name}/start"), response_model=SuccessResponse)
def start_container(name: str):
    container = docker_container_get(name)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    container.start()
    return SuccessResponse(success=True)


@container.get(expand_api_url("{name}/stop"))
def stop_container(name: str):
    container = docker_container_get(name)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    container.stop()
    return SuccessResponse(success=True)


@container.post(expand_api_url("create/{template_name}"), response_model=SuccessResponse)
def create_container(template_name: str):
    template = get_template(template_name)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    # TODO: add ports and volumes, most times it will be None.
    docker_container_create(template.name, template.image, None, None)


@container.get(expand_api_url("{container_name}/status"), response_model=RunningResponse)
def get_container_status(container_name: str):
    container = docker_container_get(container_name)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    return RunningResponse(running=docker_container_running(container))


def _cpu_percent(metric: dict[str, Any]) -> float:
    total_usage_current = metric["cpu_stats"]["cpu_usage"]["total_usage"]
    total_usage_prev = metric["precpu_stats"]["cpu_usage"]["total_usage"]
    total_system_current = metric["cpu_stats"]["system_cpu_usage"]

    total_system_prev = metric["precpu_stats"].get("system_cpu_usage", 0)
    cpu_percent = (total_usage_current - total_usage_prev) / (total_system_current - total_system_prev) * 100
    return trunc(cpu_percent * 100) / 100


async def pruned_metrics(container: Container):
    if container.status == "running":
        metrics = container.stats(stream=True, decode=True)
        for metric in metrics:
            # cpu percent, mem percent, net_rx, net_tx, disk_rx, disk_tx, disk_total
            data = [
                _cpu_percent(metric),
                round(metric["memory_stats"]["usage"] / metric["memory_stats"]["limit"] * 100, 2),
                metric["networks"]["eth0"]["rx_bytes"],
                metric["networks"]["eth0"]["tx_bytes"],
                metric["blkio_stats"]["io_service_bytes_recursive"][0]["value"],
                metric["blkio_stats"]["io_service_bytes_recursive"][1]["value"],
            ]
            yield f"{data}\n"
            await asyncio.sleep(10)


@container.get(expand_api_url("{container_name}/metrics"))
def get_container_metrics(container_name: str):
    container = docker_container_get(container_name)
    if not container:
        raise HTTPException(status_code=404, detail="Container not found")
    return StreamingResponse(pruned_metrics(container), media_type="text/plain")


@container.get(expand_api_url("{container_name}/logs"))
def get_log_message(container_name: str, line_count: int | None = None):
    # output last {line_count} lines before outputing stream
    container = docker_container_get(container_name)
    if not container:
        raise HTTPException(status_code=404, detail="Container not Found.")
    if line_count is None:
        line_count = 1
    return docker_container_logs(container, line_count)
