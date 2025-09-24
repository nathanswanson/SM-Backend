"""
nodes_api.py

API endpoints for node information like hardware, disk usage, runtime, ping

Author: Nathan Swanson
"""

import subprocess

from fastapi import APIRouter

from server_manager.webservice.db_models import Nodes
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.util import expand_api_url

system = APIRouter(tags=["nodes"])


@system.get(expand_api_url("hardware"), response_model=Nodes)
def hardware() -> Nodes | None:
    """return hardware information in form of a Nodes object
    fields: id, name, architecture, cpu_cores, memory, disk, cpu_name"""
    return DB().get_node("RPI 01")


@system.get(expand_api_url("disk_usage"), response_model=tuple[int, int])
def disk_usage():
    """return disk usage in bytes (used, total)"""
    command = ["df", "-l", "--exclude={tmpfs,devtmpfs}", "--total"]
    ret = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    if ret is None or ret.stdout is None:
        return (-1, -1)
    output = ret.stdout.decode("utf-8").strip().split("\n")[-1].split()
    return output[2], output[3]


@system.get(expand_api_url("runtime"), response_model=int)
def runtime():
    """return runtime in hours"""
    command = ["/usr/bin/uptime"]
    ret = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    if ret is None or ret.stdout is None:
        return -1
    output = ret.stdout.decode("utf-8").split(" ")
    return int(output[3]) * 24 + int(output[5].strip(",").split(":")[0])


@system.get(expand_api_url("ping"))
def ping():
    return True
