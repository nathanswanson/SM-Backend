from typing import Optional

from sqlalchemy import JSON, Column, Integer
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, Relationship, SQLModel


class ServerUserLink(SQLModel, table=True):
    server_id: Optional[int] = Field(default=None, foreign_key="servers.id", primary_key=True, description="Server ID")
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True, description="User ID")


class TemplatesBase(SQLModel):
    name: str = Field(index=True, nullable=False, unique=True, description="Template name")
    image: str = Field(nullable=False, description="Docker image name")
    tags: list[str] = Field(
        description="Comma-separated tags for the template",
        sa_column=Column(JSON),
    )
    default_env: dict[str, str] | None = Field(
        description="JSON string of default environment variables",
        sa_column=Column(JSON),
    )
    user_env: dict[str, str] | None = Field(
        description='JSON string of "Modules" that will be added to server creator UI',
        sa_column=Column(JSON),
    )

    resource_min_cpu: int | None = Field(description="Minimum CPU resources required")
    resource_min_disk: int | None = Field(description="Minimum Disk resources required")
    resource_min_mem: int | None = Field(description="Minimum Memory resources required")


class Templates(TemplatesBase, table=True):
    # sql specific
    id: int | None = Field(primary_key=True, default=None, description="Template ID")
    linked_servers: list["Servers"] = Relationship(back_populates="server_template")
    exposed_port: list[int] = Field(
        description="List of ports exposed by the template", sa_column=Column(ARRAY(Integer))
    )


class TemplatesCreate(TemplatesBase):
    pass


class TemplatesRead(TemplatesBase):
    id: int


class UsersBase(SQLModel):
    username: str = Field(index=True, nullable=False, unique=True, description="Username")
    disabled: bool = Field(default=True)
    admin: bool = Field(default=False)


class Users(UsersBase, table=True):
    # sql specific
    id: Optional[int] = Field(primary_key=True, nullable=False, unique=True, description="User ID")
    linked_servers: list["Servers"] = Relationship(back_populates="linked_users", link_model=ServerUserLink)

    # private fields
    hashed_password: str


class UsersCreate(UsersBase):
    pass


class UsersRead(UsersBase):
    id: int


class NodesBase(SQLModel):
    # node info
    name: str = Field(index=True, nullable=False, unique=True, description="Node name")
    cpus: int = Field(description="Number of CPUs on the node")
    disk: int = Field(description="Total disk space on the node in GB")
    memory: int = Field(description="Total memory on the node in GB")
    cpu_name: str = Field(description="CPU model name")
    max_hz: int = Field(description="Maximum CPU frequency on the node in MHz")
    arch: str = Field(description="Node architecture")


class Nodes(NodesBase, table=True):
    # sql specific
    id: Optional[int] = Field(primary_key=True, nullable=False, unique=True, description="Node ID")
    child_servers: list["Servers"] = Relationship(back_populates="server_node")


class NodesCreate(NodesBase):
    pass


class NodesRead(NodesBase):
    id: int


class ServersBase(SQLModel):
    name: str = Field(index=True, nullable=False, unique=True, description="Server name")
    env: dict[str, str] = Field(
        description="JSON string of environment variables for the server",
        sa_column=Column(JSON),
    )
    cpu: int | None = Field(description="CPU resources allocated to the server")
    disk: int | None = Field(description="Disk space allocated to the server in GB")
    memory: int | None = Field(description="Memory allocated to the server in GB")
    container_name: str = Field(description="Docker container name for the server", default="")
    node_id: int = Field(foreign_key="nodes.id")
    template_id: int = Field(foreign_key="templates.id")


class Servers(ServersBase, table=True):
    # sql specific
    id: Optional[int] = Field(primary_key=True, default=None, description="Server ID")
    server_node: "Nodes" = Relationship(back_populates="child_servers")
    server_template: "Templates" = Relationship(back_populates="linked_servers")
    linked_users: list[Users] = Relationship(back_populates="linked_servers", link_model=ServerUserLink)
    port: Optional[list[int]] = Field(description="List of port exposed by proxy", sa_column=Column(ARRAY(Integer)))


class ServersCreate(ServersBase):
    pass


class ServersRead(ServersBase):
    id: int
    node_id: int = Field(foreign_key="nodes.id")
    template_id: int = Field(foreign_key="templates.id")
    port: list[int]
