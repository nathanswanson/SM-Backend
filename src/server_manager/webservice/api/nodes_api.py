"""
nodes_api.py

API endpoints for node information like hardware, disk usage, runtime, ping

Author: Nathan Swanson
"""

import datetime
import logging
import re
import subprocess

from fastapi import APIRouter

from server_manager.webservice.db_models import Nodes
from server_manager.webservice.models import NodeDiskUsageResponse, NodePingResponse, NodeUptimeResponse
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.util import expand_api_url

system = APIRouter(tags=["nodes"])
_runtime_pattern = re.compile(
    r"^\s*\d+:\d+:\d+ up (\d+) days?,\s+(\d+):\d+,\s+\d+\susers?,\s+load\s+average:\s+\d\.\d\d,\s+\d\.\d\d,\s+\d\.\d\d"
)


@system.get(expand_api_url("hardware"), response_model=Nodes)
def hardware() -> Nodes | None:
    """return hardware information in form of a Nodes object
    fields: id, name, architecture, cpu_cores, memory, disk, cpu_name"""
    return DB().get_node("RPI 01")


@system.get(expand_api_url("disk_usage"), response_model=NodeDiskUsageResponse)
def disk_usage():
    """return disk usage in bytes (used, total)"""
    command = ["df", "-l", "--exclude={tmpfs,devtmpfs}", "--total"]
    ret = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    if ret is None or ret.stdout is None:
        return (-1, -1)
    output = ret.stdout.decode("utf-8").strip().split("\n")[-1].split()
    used_disk = int(output[2] or -1)
    total_disk = int(output[3] or -1)
    if used_disk < 0 or total_disk < 0:
        logging.error("Error parsing disk usage output: %s", output)
    return NodeDiskUsageResponse(used=used_disk, total=total_disk)


@system.get(expand_api_url("runtime"), response_model=NodeUptimeResponse)
def runtime():
    """return runtime in hours"""
    command = ["/usr/bin/uptime"]
    ret = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    if ret is None or ret.stdout is None:
        return -1
    output = ret.stdout.decode("utf-8")
    matches = _runtime_pattern.match(output)
    if not matches:
        return -1
    time = int(matches.group(1)) * 24 + int(matches.group(2))

    try:
        return NodeUptimeResponse(uptime_hours=int(time))
    except (IndexError, ValueError):
        logging.exception("Error parsing uptime output: %s", output)
        return NodeUptimeResponse(uptime_hours=-1)


@system.get(expand_api_url("ping"), response_model=NodePingResponse)
def ping():
    """ping the server"""
    return NodePingResponse(recieved_at=int(datetime.datetime.now(tz=datetime.UTC).timestamp()))
