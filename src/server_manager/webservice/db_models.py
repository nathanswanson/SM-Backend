from sqlmodel import Field, SQLModel


class Templates(SQLModel, table=True):
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


class Users(SQLModel, table=True):
    username: str = Field(primary_key=True)
    disabled: bool | None = Field(default=False)
    admin: bool | None = Field(default=False)
    hashed_password: str


class Nodes(SQLModel, table=True):
    cpus: int = Field(description="Number of CPUs on the node")
    disk: int = Field(description="Total disk space on the node in GB")
    memory: int = Field(description="Total memory on the node in GB")
    cpu_name: str = Field(description="CPU model name")
    max_hz: int = Field(description="Maximum CPU frequency on the node in MHz")
    id: str = Field(primary_key=True, nullable=False, unique=True, description="Node name")
    arch: str = Field(description="Node architecture")
