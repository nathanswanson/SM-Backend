# SPDX-FileCopyrightText: 2025-present NS <nathanswanson370@gmail.com>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import click
import uvicorn
from rich import print
from rich.console import Console

from server_manager.__about__ import __version__
from server_manager.cli.completion.container_auto import ContainerAutoType
from server_manager.cli.completion.image_auto import ImageAutoType
from server_manager.webservice.docker_interface.docker_container_api import (
    docker_list_containers_names,
    docker_remove_container,
    docker_stop_container,
)
from server_manager.webservice.docker_interface.docker_image_api import (
    docker_get_env_vars,
    docker_get_image,
    docker_image_exists,
    docker_image_spawn_container,
    docker_list_images,
    docker_pull_image,
)
from server_manager.webservice.webservice import app

console = Console()


def _varargs_to_dict(varargs_str) -> dict[str, str]:
    """Convert a list of VAR=VALUE strings to a dictionary."""
    env_dict = {}
    for item in varargs_str:
        item: str
        pair = item.split("=", 1)
        key = pair[0]
        value = pair[1] if len(pair) > 1 else ""
        env_dict[key] = value
    return env_dict


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="server_manager")
@click.option("--dev", is_flag=True, help="Run in development mode")
@click.pass_context
def server_manager(ctx, dev):
    if ctx.invoked_subcommand is None:
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=dev)


@server_manager.group("image")
@click.argument("image_id", type=ImageAutoType())
@click.pass_context
def image(ctx, image_id: str):
    """Manage Docker images."""
    print(image_id)
    ctx.ensure_object(dict)
    if not docker_image_exists(image_id):
        console.print(f"[red]Image with ID {image_id} does not exist.[/red]")
        ctx.exit(1)
    ctx.obj["image_id"] = image_id


@image.command("pull")
@click.pass_context
def pull_image(ctx):
    image_id = ctx.obj["image_id"]
    task = docker_pull_image(image_id)
    with console.status("Pulling image..."):
        if task:
            console.print(f"[green]Successfully pulled image:[/green] {image_id}")
        else:
            console.print(f"[red]Failed to pull image:[/red] {image_id}")
    console.print("Done!" if task else "Failed!")


@image.command("get-env")
@click.pass_context
def get_env_vars(ctx):
    image_id = ctx.obj["image_id"]
    env_vars = docker_get_env_vars(image_id)
    if not env_vars:
        console.print(f"[red]No environment variables found for image:[/red] {image_id}")
    else:
        console.print(f"[bold]Environment Variables for {image_id}:[/bold]")
        for key, value in env_vars.items():
            console.print(f"{key}={value if value is not None else 'None'}")


@image.command(
    "create-container",
    short_help="Run a Docker image",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.option("--server-name", required=True, help="Name of the server to create")
@click.pass_context
def create_container(ctx, server_name: str):
    image_id = ctx.obj["image_id"]
    # if int use as index in list
    # also check if its a string that can be converted to int
    try:
        image_id_int = int(image_id)
        image_id = docker_list_images()[image_id_int - 1]
    except ValueError:
        pass
    if not isinstance(image_id, str):
        console.print(f"[red]Invalid image ID: {image_id}[/red]")
        return

    if not docker_image_exists(image_id):
        console.print(f"[yellow]Image with ID {image_id} does not exist, pulling...[/yellow]")
        if not docker_pull_image(image_id):
            console.print(f"[red]Failed to pull image with ID {image_id}.[/red]")
            return

    env = _varargs_to_dict(ctx.args)
    image_obj = docker_get_image(image_id)
    if not image_obj:
        console.print(f"[red]Image with ID {image_id} not found.[/red]")
        return
    docker_image_spawn_container(image_obj, server_name, env)
    console.print(f"[bold]Creating server with image {image_id} and environment variables:[/bold]")
    for key, value in env.items():
        console.print(f"{key}={value}")


@server_manager.group("container")
@click.argument("container_name", type=ContainerAutoType())
@click.pass_context
def container(ctx, container_name: str):
    """Manage Docker containers."""
    ctx.ensure_object(dict)
    ctx.obj["container_name"] = container_name


@container.command("stop")
@click.pass_context
def stop_container(ctx):
    container_name = ctx.obj["container_name"]
    task = docker_stop_container(container_name)
    with console.status("Stopping container..."):
        if task:
            console.print(f"[green]Successfully stopped container:[/green] {container_name}")
        else:
            console.print(f"[red]Failed to stop container:[/red] {container_name}")
    console.print("Done!" if task else "Failed!")


@container.command("remove")
@click.pass_context
def remove_container(ctx):
    container_name = ctx.obj["container_name"]
    task = docker_remove_container(container_name)
    with console.status("Removing container..."):
        if task:
            console.print(f"[green]Successfully removed container:[/green] {container_name}")
        else:
            console.print(f"[red]Failed to remove container:[/red] {container_name}")
    console.print("Done!" if task else "Failed!")


# @server_manager.command("list")
# @click.argument("choice", type=click.Choice(["images", "containers", "templates"]))
# def list_resources(choice: str):
#     if choice == "images":
#         console.print(docker_list_images())
#     elif choice == "containers":
#         console.print(docker_list_containers_names())
#     elif choice == "templates":
#         console.print(TemplateManager().get_templates())


# @server_manager.group("template")
# def template_group():
#     """Manage server templates."""


# @template_group.command("create", context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
# @click.argument("name")
# @click.argument("description")
# @click.argument("image")
# @click.option("--tags")
# @click.option("--cpu", type=int)
# @click.option("--memory", type=str)
# @click.option("--extra-args")
# @click.pass_context
# def create_template(
#     ctx, name: str, description: str, image: str, tags: list[str], cpu: int, memory: str, extra_args: list[str]
# ):
#     """Create a new server template."""
#     console.print(f"Creating server template: {name}")
#     console.print(f"Description: {description}")
#     console.print(f"Image: {image}")
#     console.print(f"Tags: {tags}")
#     console.print(f"CPU: {cpu}")
#     console.print(f"Memory: {memory}")
#     console.print(f"Extra Args: {extra_args}")
#     env = _varargs_to_dict(ctx.args)

#     TemplateManager().create_template(name, description, image, tags, cpu, memory, env, extra_args)


# @template_group.command("remove")
# @click.argument("name")
# def remove_template(name: str):
#     """Remove a server template."""
#     console.print(f"Removing server template: {name}")


# @template_group.command("edit", context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
# @click.argument("name")
# @click.option("--editor", is_flag=True)
# @click.option("--description")
# @click.option("--image")
# def edit_template(name: str, editor: bool, description: str, image: str):  # noqa: FBT001
#     # if editor ignore everything else
#     if editor:
#         click.edit(filename=TemplateManager().get_template_path(name))
#     else:
#         print(description, image)


# @template_group.command("show")
# @click.argument("name")
# def show_template(name: str):
#     console.print(TemplateManager().get_template(name))
