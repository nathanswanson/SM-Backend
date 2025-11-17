"""
nodes_api.py

API endpoints for node information like hardware, disk usage, runtime, ping

Author: Nathan Swanson
"""

import re
import subprocess
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server_manager.webservice.db_models import NodesCreate, NodesRead
from server_manager.webservice.logger import sm_logger
from server_manager.webservice.models import NodeDiskUsageResponse, NodeUptimeResponse
from server_manager.webservice.util.data_access import DB, get_db

router = APIRouter()
_runtime_pattern = re.compile(
    r"^\s*\d+:\d+:\d+ up (\d+) days?,\s+(\d+):\d+,\s+\d+\susers?,\s+load\s+average:\s+\d\.\d\d,\s+\d\.\d\d,\s+\d\.\d\d"
)


@router.post("/", response_model=NodesRead)
def add_node(node: NodesCreate, db: Annotated[DB, Depends(get_db)]) -> NodesRead | None:
    """add a new node"""
    ret = db.create_node(node)
    if ret:
        return ret
    return None


@router.get("/{node_id}", response_model=NodesRead)
def get_node(
    node_id: int,
    db: Annotated[DB, Depends(get_db)],
) -> NodesRead | None:
    """return hardware information in form of a Nodes object
    fields: id, name, architecture, cpu_cores, memory, disk, cpu_name"""
    ret = db.get_node(node_id)
    if ret is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return ret


@router.delete("/{node_id}")
def delete_node(node_id: int) -> dict:  # noqa: ARG001
    """delete a node by name"""
    return {"success": False, "error": "Not implemented"}


@router.get("/{node_id}/disk_usage", response_model=NodeDiskUsageResponse)
def disk_usage(node_id: int):  # noqa: ARG001
    """return disk usage in bytes (used, total)"""
    command = ["df", "-l", "--exclude={tmpfs,devtmpfs}", "--total"]
    ret = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    if ret is None or ret.stdout is None:
        return NodeDiskUsageResponse(used=-1, total=-1)
    output = ret.stdout.decode("utf-8").strip().split("\n")[-1].split()
    used_disk = int(output[2] or -1)
    total_disk = int(output[3] or -1)
    if used_disk < 0 or total_disk < 0:
        sm_logger.error("Error parsing disk usage output: %s", output)
    return NodeDiskUsageResponse(used=used_disk, total=total_disk)


@router.get("/{node_id}/runtime", response_model=NodeUptimeResponse)
def runtime(node_id: int):  # noqa: ARG001
    """return runtime in hours"""
    command = ["/usr/bin/uptime"]
    ret = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    if ret is None or ret.stdout is None:
        return NodeUptimeResponse(uptime_hours=-1)
    output = ret.stdout.decode("utf-8")
    matches = _runtime_pattern.match(output)
    if not matches:
        return NodeUptimeResponse(uptime_hours=-1)
    time = int(matches.group(1)) * 24 + int(matches.group(2))

    try:
        return NodeUptimeResponse(uptime_hours=int(time))
    except (IndexError, ValueError):
        sm_logger.exception("Error parsing uptime output: %s", output)
        return NodeUptimeResponse(uptime_hours=-1)
