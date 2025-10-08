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


class UserPublic(SQLModel):
    username: str = Field(primary_key=True, nullable=False, unique=True, description="Username")
    disabled: bool | None = None
    admin: bool | None = None


class Users(UserPublic, table=True):
    hashed_password: str


class Nodes(SQLModel, table=True):
    cpus: int = Field(description="Number of CPUs on the node")
    disk: int = Field(description="Total disk space on the node in GB")
    memory: int = Field(description="Total memory on the node in GB")
    cpu_name: str = Field(description="CPU model name")
    max_hz: int = Field(description="Maximum CPU frequency on the node in MHz")
    id: str = Field(primary_key=True, nullable=False, unique=True, description="Node name")
    arch: str = Field(description="Node architecture")


class Servers(SQLModel, table=True):
    id: str = Field(primary_key=True, nullable=False, unique=True, description="Server ID")
    name: str = Field(nullable=False, unique=True, description="Server name")
    owner: str = Field(nullable=False, description="Owner username")
    node: str = Field(nullable=False, description="Node name where the server is hosted")
    template: str = Field(nullable=False, description="Template name used for the server")
    env: str | None = Field(description="JSON string of environment variables for the server")
    cpu: int = Field(description="CPU resources allocated to the server")
    disk: int = Field(description="Disk space allocated to the server in GB")
    memory: int = Field(description="Memory allocated to the server in GB")
    port: int | None = Field(description="Port number assigned to the server")
