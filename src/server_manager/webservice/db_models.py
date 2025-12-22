from typing import Optional

from sqlalchemy import JSON, Column, Integer
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, Relationship, SQLModel


class ServerUserLink(SQLModel, table=True):
    server_id: Optional[int] = Field(default=None, foreign_key="servers.id", primary_key=True, description="Server ID")
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True, description="User ID")


class TemplateUserLink(SQLModel, table=True):
    template_id: Optional[int] = Field(
        default=None, foreign_key="templates.id", primary_key=True, description="Template ID"
    )
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True, description="User ID")


class NodeUserLink(SQLModel, table=True):
    node_id: Optional[int] = Field(default=None, foreign_key="nodes.id", primary_key=True, description="Node ID")
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True, description="User ID")


class UsersGroupUsersLink(SQLModel, table=True):
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", primary_key=True, description="User ID")
    group_id: Optional[int] = Field(
        default=None, foreign_key="usersgroup.id", primary_key=True, description="User Group Scope ID"
    )


class TemplatesBase(SQLModel):
    name: str = Field(index=True, nullable=False, unique=True, description="Template name")
    image: str = Field(nullable=False, description="Docker image name")
    tags: list[str] = Field(
        description="Comma-separated tags for the template",
        sa_column=Column(JSON),
    )
    exposed_port: list[int] = Field(
        description="List of ports that are exposed by the template",
        sa_column=Column(ARRAY(Integer)),
    )
    exposed_volume: list[str] | None = Field(
        default=None, description="List of volumes that are exposed by the template.", sa_column=Column(JSON)
    )
    modules: list[str] | None = Field(
        description='JSON string of "Modules" that will be added to server creator UI',
        sa_column=Column(JSON),
    )
    description: str | None = Field(description="Template description", default=None)
    resource_min_cpu: int | None = Field(description="Minimum CPU resources required")
    resource_min_disk: int | None = Field(description="Minimum Disk resources required")
    resource_min_mem: int | None = Field(description="Minimum Memory resources required")


class Templates(TemplatesBase, table=True):
    # sql specific
    id: int | None = Field(primary_key=True, default=None, description="Template ID")
    linked_servers: list["Servers"] = Relationship(back_populates="server_template")
    linked_users: list["Users"] = Relationship(back_populates="linked_templates", link_model=TemplateUserLink)


class TemplatesCreate(TemplatesBase):
    pass


class TemplatesRead(TemplatesBase):
    id: int


class UsersGroupBase(SQLModel):
    group_name: str = Field(index=True, nullable=False, unique=True, description="User Group Name")


class UsersGroup(UsersGroupBase, table=True):
    id: Optional[int] = Field(primary_key=True, default=None, nullable=False, description="User Group Scope ID")

    scopes: list[str] | None = Field(description="List of scopes assigned to the user group ", sa_column=Column(JSON))
    linked_users: list["Users"] = Relationship(back_populates="linked_user_groups", link_model=UsersGroupUsersLink)


class UsersGroupCreate(UsersGroupBase):
    pass


class UsersGroupRead(UsersGroupBase):
    id: int


class UsersBase(SQLModel):
    username: str = Field(index=True, nullable=False, unique=True, description="Username")
    disabled: bool = Field(default=True)
    scopes: list[str] | None = Field(description="List of scopes assigned to the user ", sa_column=Column(JSON))
    admin: bool = Field(default=False)


class Users(UsersBase, table=True):
    # sql specific
    id: Optional[int] = Field(primary_key=True, nullable=False, unique=True, default=None, description="User ID")
    linked_servers: list["Servers"] = Relationship(back_populates="linked_users", link_model=ServerUserLink)
    linked_templates: list["Templates"] = Relationship(back_populates="linked_users", link_model=TemplateUserLink)
    linked_nodes: list["Nodes"] = Relationship(back_populates="linked_users", link_model=NodeUserLink)
    linked_user_groups: list["UsersGroup"] = Relationship(back_populates="linked_users", link_model=UsersGroupUsersLink)
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
    id: Optional[int] = Field(primary_key=True, nullable=False, default=None, unique=True, description="Node ID")
    child_servers: list["Servers"] = Relationship(back_populates="server_node")
    linked_users: list["Users"] = Relationship(back_populates="linked_nodes", link_model=NodeUserLink)


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
    tags: list[str] = Field(
        description="Comma-separated tags for the server",
        sa_column=Column(JSON),
        default=[],
    )
    linked_users: list[Users] = Relationship(back_populates="linked_servers", link_model=ServerUserLink)


class Servers(
    ServersBase,
    table=True,
):
    # sql specific
    id: Optional[int] = Field(primary_key=True, default=None, description="Server ID")
    server_node: "Nodes" = Relationship(back_populates="child_servers")
    server_template: "Templates" = Relationship(back_populates="linked_servers")
    port: list[int] = Field(description="List of port exposed by proxy", sa_column=Column(ARRAY(Integer)))


class ServersCreate(ServersBase):
    pass


class ServersRead(ServersBase):
    id: int
    node_id: int = Field(foreign_key="nodes.id")
    template_id: int = Field(foreign_key="templates.id")
    port: list[int]
