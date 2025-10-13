import builtins
import contextlib
import json
import os
from http import HTTPStatus

import requests

from server_manager.webservice.db_models import Servers
from server_manager.webservice.docker_interface.docker_container_api import docker_container_name_exists
from server_manager.webservice.logger import sm_logger
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.singleton import SingletonMeta

CADDY_URL = "http://rproxy:2019"
start_port = int(os.environ.get("SM_PORT_START", "30000"))
end_port = int(os.environ.get("SM_PORT_END", "30100"))


def _container_new_config_url(container_name: str):
    return f"{CADDY_URL}/config/apps/layer4/servers/{container_name}"


def _container_exists_config_url(container_name: str):
    return f"{CADDY_URL}/id/{container_name}"


class ServerRouter(metaclass=SingletonMeta):
    def __init__(self):
        # add empty servers {} to layer4
        requests.post(f"{CADDY_URL}/config/apps/layer4/servers", json={}, timeout=5)
        self.used_ports: set[int] = set()

    def allocate_port(self) -> int | None:
        for port in range(start_port, end_port + 1):
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port
        sm_logger.error("No available ports in the range %d-%d", start_port, end_port)
        return None

    def release_port(self, port: int):
        self.used_ports.discard(port)

    def add_caddy_route(self, container_name: str, port_mappings: dict[int, int]):
        # Function to add a Caddy route for the given container
        # TODO: support more then one mapping
        (port_container, port_caddy) = port_mappings.popitem()
        sm_logger.debug("Adding Caddy route for container: %s on port %d", container_name, port_caddy)

        contents: dict = {}
        contents["@id"] = container_name
        contents["listen"] = [f":{port_caddy}"]
        contents["routes"] = [
            {
                "handle": [
                    {
                        "handler": "proxy",
                        "upstreams": [
                            {
                                "dial": [f"{container_name}:{port_container}"],
                            },
                        ],
                    },
                ],
            }
        ]
        with contextlib.suppress(builtins.BaseException):
            response = requests.post(
                _container_new_config_url(container_name),
                json=contents,
                timeout=5,
                headers={"Content-Type": "application/json"},
            )
            sm_logger.debug("Caddy response: %s", json.dumps(response.json(), indent=2))
            return response.status_code == HTTPStatus.OK
        return False

    def ping_caddy(self) -> bool:
        try:
            response = requests.get(f"http://{CADDY_URL}/config", timeout=5)

            if response.status_code == requests.HTTPError:
                sm_logger.error("Caddy ping failed with status code: %s", response.status_code)
                return False
        except requests.RequestException:
            sm_logger.exception("Error pinging Caddy")
        else:
            return response.status_code == HTTPStatus.OK
        return False

    def delete_caddy_route(self, container_name: str) -> bool:
        try:
            response = requests.delete(_container_exists_config_url(container_name), timeout=5)
        except requests.RequestException:
            sm_logger.exception("Error deleting Caddy route for container: %s", container_name)
            return False
        else:
            return response.status_code == HTTPStatus.OK

    def open_ports(self, server: Servers) -> bool:
        # docker -> caddy no port forward, docker network instead.
        # exposed ports should not be changed. minecraft example:
        # exposed (internal)25565 -> (docker net)25565 -> (caddy)30050
        #             container_name:25565 -> host_name:30050
        # template tracks the exposed port, server the caddy port
        if server is None:
            sm_logger.warning("Server %s has no ports to open.", server.name)
            return False
        template = DB().get_template(server.template_id)
        if docker_container_name_exists(server.container_name) and template and template.exposed_port and server.port:
            try:
                return self.add_caddy_route(
                    server.container_name, dict(zip(template.exposed_port, server.port, strict=True))
                )
            except ValueError as e:
                sm_logger.error("Error opening ports for server %s: %s", server.name, e)
        return False
