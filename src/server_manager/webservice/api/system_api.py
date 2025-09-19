import json
import subprocess
from functools import lru_cache

from fastapi import APIRouter

from server_manager.webservice.models import HardwareInfoResponse
from server_manager.webservice.util.util import expand_api_url

system = APIRouter(tags=["system"])


@lru_cache
def lscpu_json():
    ret = subprocess.run(["/usr/bin/lscpu", "--json"], capture_output=True, text=True, check=False).stdout.strip()
    pruned = {}
    hw_json = json.loads(ret)

    def resolved_json(position: int):
        return hw_json["lscpu"][position]["data"]

    pruned["model_name"] = resolved_json(0)
    pruned["architecture"] = resolved_json(7)
    pruned["cpu_count"] = resolved_json(4)
    pruned["threads_per_core"] = resolved_json(10)
    return pruned


@lru_cache
def lsmem_json():
    ret = subprocess.run(
        ["/usr/bin/awk", "/MemTotal/ {print $2}", "/proc/meminfo"], check=False, capture_output=True, text=True
    ).stdout.strip()
    return json.loads(ret)


@system.get(expand_api_url("hardware"), response_model=HardwareInfoResponse)
def hardware():
    # cpu-name
    cpu_data = HardwareInfoResponse.CPUHardwareResponse(**lscpu_json())
    mem_data = lsmem_json()
    return HardwareInfoResponse(mem=mem_data, cpu=cpu_data)


@system.get(expand_api_url("ping"))
def ping():
    return True
