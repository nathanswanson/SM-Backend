import json
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RootFS:
    type: str
    layers: Optional[list[str]] = None
    base_layer: Optional[str] = None


@dataclass
class GraphDriverData:
    name: str
    data: dict[str, Any]


@dataclass
class DockerImageInspect:
    id: str
    repo_tags: Optional[list[str]] = None
    repo_digests: Optional[list[str]] = None
    parent: Optional[str] = None
    comment: Optional[str] = None
    created: str = ""
    container: Optional[str] = None
    container_config: Optional[dict[str, Any]] = None
    docker_version: Optional[str] = None
    author: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    architecture: str = ""
    os: str = ""
    size: int = 0
    virtual_size: int = 0
    graph_driver: Optional[GraphDriverData] = None
    root_fs: Optional[RootFS] = None
    metadata: Optional[dict[str, Any]] = None


def from_json(data: str) -> DockerImageInspect:
    """Deserialize from Docker image inspect JSON string"""
    obj = json.loads(data)

    return DockerImageInspect(
        id=obj.get("Id"),
        repo_tags=obj.get("RepoTags"),
        repo_digests=obj.get("RepoDigests"),
        parent=obj.get("Parent"),
        comment=obj.get("Comment"),
        created=obj.get("Created", ""),
        container=obj.get("Container"),
        container_config=obj.get("ContainerConfig"),
        docker_version=obj.get("DockerVersion"),
        author=obj.get("Author"),
        config=obj.get("Config"),
        architecture=obj.get("Architecture", ""),
        os=obj.get("Os", ""),
        size=obj.get("Size", 0),
        virtual_size=obj.get("VirtualSize", 0),
        graph_driver=GraphDriverData(**obj["GraphDriver"]) if "GraphDriver" in obj else None,
        root_fs=RootFS(**obj["RootFS"]) if "RootFS" in obj else None,
        metadata=obj.get("Metadata"),
    )
