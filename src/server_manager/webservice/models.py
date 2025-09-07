from typing import Annotated

from pydantic import BaseModel, Field


# Containers
class ContainerListResponse(BaseModel):
    container: list[str]

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


# Templates
class TemplateListResponse(BaseModel):
    template: list[str]

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


class Resource(BaseModel):
    cpu: Annotated[
        float | None,
        Field(
            description="The number of CPU cores allocated to the container.",
            ge=1.0,
            le=4.0,
        ),
    ] = 2
    memory: Annotated[
        str | None,
        Field(
            description="The amount of memory allocated to the container, e.g., '2G' for 2 gigabytes.",
            pattern="^[0-9]+[KMG]?$",
        ),
    ] = "1G"


class Template(BaseModel):
    class Config:
        extra = "forbid"

    name: Annotated[str, Field(description="The name of the template.")]
    image: Annotated[str, Field(description="The name of the Docker image to use for the container.")]
    tags: Annotated[
        list[str] | None,
        Field(description="Additional Tags for the Docker image. defaults to 'latest'."),
    ] = None
    description: Annotated[str | None, Field(description="A brief description of the template.")] = None
    resource: Annotated[
        Resource | None,
        Field(description="Minimum resource requirements/allocated for the container."),
    ] = None
    env: list[str | dict[str, str]] | None = None


class HardwareInfoResponse(BaseModel):
    class CPUHardwareResponse(BaseModel):
        architecture: str
        cpu_count: int
        model_name: str
        threads_per_core: int

    cpu: CPUHardwareResponse
    mem: int


class ContainerCreateRequest(BaseModel):
    server_name: str
    template: str
    port: dict[str, int | None] | None
    env: dict[str, str]


class ContainerStatusResponse(BaseModel):
    status: str


class SuccessResponse(BaseModel):
    success: bool


class RunningResponse(BaseModel):
    running: bool
