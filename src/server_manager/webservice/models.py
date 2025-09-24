from fastapi import UploadFile
from pydantic import BaseModel, SecretStr

## generic


class SuccessModel(BaseModel):
    success: bool


class StringListModel(BaseModel):
    items: list[str]


class StringModel(BaseModel):
    item: str


## Containers
class ContainerListResponse(StringListModel):
    pass


class ContainerCreateRequest(BaseModel):
    server_name: str
    template: str
    port: dict[str, int | None] | None
    env: dict[str, str]


class ContainerCreateResponse(SuccessModel):
    pass


class ContainerDeleteResponse(SuccessModel):
    pass


class ContainerStartResponse(SuccessModel):
    pass


class ContainerStopResponse(SuccessModel):
    pass


class ContainerStatusResponse(BaseModel):
    running: bool


class ContainerLogsResponse(StringListModel):
    pass


class ContainerFileDeleteResponse(SuccessModel):
    pass


class ContainerFileListResponse(StringListModel):
    pass


class ContainerFileUploadRequest(BaseModel):
    path: str
    file: UploadFile


class ContainerFileUploadResponse(SuccessModel):
    pass


class ContainerCommandResponse(SuccessModel):
    pass


## Template


class TemplateListResponse(StringListModel):
    pass


class TemplateCreateResponse(SuccessModel):
    pass


class TemplateDeleteRequest(StringModel):
    pass


class TemplateDeleteResponse(SuccessModel):
    pass


## Auth


class Token(BaseModel):
    access_token: str
    token_type: str
    expire_time: int | None = None


class TokenData(BaseModel):
    username: str


class CreateUserRequest(BaseModel):
    username: str
    password: SecretStr


## Nodes


class NodeUptimeResponse(BaseModel):
    uptime_hours: int


class NodeDiskUsageResponse(BaseModel):
    total: int
    used: int


class NodePingResponse(BaseModel):
    recieved_at: int
