from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from aiodocker import DockerError

from server_manager.webservice.interface.docker import docker_image_api


def _patch_docker_client(mocker, client):
    @asynccontextmanager
    async def _ctx():
        yield client

    mocker.patch("server_manager.webservice.interface.docker.docker_image_api.docker_client", _ctx)


class DummyImages:
    def __init__(self, image_data: dict, *, fail_first_get: bool = False):
        self._image_data = image_data
        self._fail_first_get = fail_first_get
        self.get_calls: list[str] = []
        self.pull_calls: list[tuple[str, str]] = []

    async def get(self, image_name: str):
        self.get_calls.append(image_name)
        if self._fail_first_get:
            self._fail_first_get = False
            raise DockerError(404, {"message": "not found"})
        return self._image_data

    async def pull(self, image_name: str, tag: str = "latest"):
        self.pull_calls.append((image_name, tag))
        return SimpleNamespace()


class DummyClient:
    def __init__(self, images: DummyImages):
        self.images = images


@pytest.mark.asyncio
async def test_docker_image_exposed_port_returns_port_list(mocker):
    image_data = {
        "Config": {
            "ExposedPorts": {
                "80/tcp": {},
                "443/tcp": {},
            }
        }
    }
    dummy_images = DummyImages(image_data)
    _patch_docker_client(mocker, DummyClient(dummy_images))

    ports = await docker_image_api.docker_image_exposed_port("nginx:latest")

    assert ports == [80, 443]
    assert dummy_images.pull_calls == []


@pytest.mark.asyncio
async def test_docker_image_exposed_port_pulls_when_missing(mocker):
    image_data = {"Config": {"ExposedPorts": {"25565/tcp": {}}}}
    dummy_images = DummyImages(image_data, fail_first_get=True)
    _patch_docker_client(mocker, DummyClient(dummy_images))

    ports = await docker_image_api.docker_image_exposed_port("minecraft:latest")

    assert ports == [25565]
    assert dummy_images.pull_calls == [("minecraft:latest", "latest")]
    assert dummy_images.get_calls.count("minecraft:latest") == 2


@pytest.mark.asyncio
async def test_docker_get_image_exposed_volumes_returns_volume_list(mocker):
    image_data = {
        "Config": {
            "Volumes": {
                "/data": {},
                "/logs": {},
            }
        }
    }
    dummy_images = DummyImages(image_data)
    _patch_docker_client(mocker, DummyClient(dummy_images))

    volumes = await docker_image_api.docker_get_image_exposed_volumes("app:latest")
    assert volumes is not None
    assert sorted(volumes) == ["/data", "/logs"]
    assert dummy_images.pull_calls == []


@pytest.mark.asyncio
async def test_docker_get_image_exposed_volumes_pulls_when_missing(mocker):
    image_data = {"Config": {"Volumes": {"/config": {}}}}
    dummy_images = DummyImages(image_data, fail_first_get=True)
    _patch_docker_client(mocker, DummyClient(dummy_images))

    volumes = await docker_image_api.docker_get_image_exposed_volumes("app:latest")

    assert volumes == ["/config"]
    assert dummy_images.pull_calls == [("app:latest", "latest")]
    assert dummy_images.get_calls.count("app:latest") == 2
