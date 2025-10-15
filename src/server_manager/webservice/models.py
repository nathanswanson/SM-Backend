from typing import Annotated

from fastapi import Form, UploadFile
from pydantic import BaseModel, SecretStr

## generic


class SuccessModel(BaseModel):
    success: bool


class StringListModel(BaseModel):
    items: list[str]


class StringModel(BaseModel):
    item: str


class StringToIDMapModel(BaseModel):
    items: dict[str, int]


## Servers
class ServerListResponse(StringToIDMapModel):
    pass


class ServerCreateRequest(BaseModel):
    server_name: str
    template: str
    port: dict[str, int | None] | None
    env: dict[str, str]


class ServerCreateResponse(SuccessModel):
    pass


class ServerDeleteResponse(SuccessModel):
    pass


class ServerStartResponse(SuccessModel):
    pass


class ServerStopResponse(SuccessModel):
    pass


class ServerStatusResponse(BaseModel):
    running: bool
    health: str | None = None


## Containers


class ContainerLogsResponse(StringListModel):
    pass


class ContainerFileDeleteResponse(SuccessModel):
    pass


class ContainerFileListResponse(StringListModel):
    pass


class ContainerFileUploadRequest(BaseModel):
    path: Annotated[str, Form()]
    file: UploadFile = Form()


class ContainerFileUploadResponse(SuccessModel):
    pass


class ContainerCommandResponse(SuccessModel):
    pass


## Template


class TemplateListResponse(StringToIDMapModel):
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


class UserListResponse(StringToIDMapModel):
    pass


## Nodes


class NodeUptimeResponse(BaseModel):
    uptime_hours: int


class NodeDiskUsageResponse(BaseModel):
    total: int
    used: int


class NodeListResponse(StringToIDMapModel):
    pass


class AuthPingResponse(BaseModel):
    recieved_at: int
