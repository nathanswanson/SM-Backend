from fastapi import APIRouter

from server_manager.webservice.db_models import Nodes
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.util import expand_api_url

system = APIRouter(tags=["system"])


def gather_stats():
    # TODO: implement node name once more then one node is supported
    return DB().get_node("RPI 01")


@system.get(expand_api_url("hardware"), response_model=Nodes)
def hardware():
    # cpu-name
    return gather_stats()


@system.get(expand_api_url("ping"))
def ping():
    return True
