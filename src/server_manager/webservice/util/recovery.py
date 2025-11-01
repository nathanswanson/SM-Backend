# links previously created sm containers to existing db entries
from server_manager.webservice.db_models import NodesCreate
from server_manager.webservice.util.data_access import DB


def recovery():
    # create node 1 if not exists
    if DB().get_node(1) is None:
        DB().create_node(
            NodesCreate(name="Node 1", cpus=4, memory=16, disk=16, cpu_name="Generic CPU", max_hz=100, arch="arm64")
        )
