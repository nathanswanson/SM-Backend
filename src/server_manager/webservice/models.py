from pydantic import BaseModel


# Containers
class StringListResponse(BaseModel):
    values: list[str]

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


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


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str
