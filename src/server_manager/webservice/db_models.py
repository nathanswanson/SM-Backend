from sqlmodel import Field, SQLModel


class Template(SQLModel, table=True):
    name: str = Field(primary_key=True, nullable=False, unique=True, description="Template name")
    image: str = Field(nullable=False, description="Docker image name")
    tags: str | None = Field(description="Comma-separated tags for the template")
    default_env: str | None = Field(description="JSON string of default environment variables")
    additional_env: str | None = Field(
        description="JSON string of environment variables that will be added to server creator"
    )
    resource_min_cpu: int | None = Field(description="Minimum CPU resources required")
    resource_min_disk: int | None = Field(description="Minimum Disk resources required")
    resource_min_mem: int | None = Field(description="Minimum Memory resources required")


class User(SQLModel, table=True):
    username: str = Field(primary_key=True)
    disabled: bool | None = Field(default=False)
    admin: bool | None = Field(default=False)
    hashed_password: str
