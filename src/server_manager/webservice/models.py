from pydantic import BaseModel


# Containers
class StringListResponse(BaseModel):
    values: list[str]

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
    }


class ContainerCreateRequest(BaseModel):
    server_name: str
    template: str
    port: dict[str, int | None] | None
    env: dict[str, str]


class Token(BaseModel):
    access_token: str
    token_type: str
    expire_time: int | None = None


class TokenData(BaseModel):
    username: str
