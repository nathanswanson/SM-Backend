# SPDX-FileCopyrightText: 2025-present NS <nathanswanson370@gmail.com>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import click
import uvicorn
from rich.console import Console

from server_manager.__about__ import __version__
from server_manager.webservice.util.auth import create_user
from server_manager.webservice.webservice import app

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="server_manager")
@click.pass_context
def server_manager(ctx):
    if not ctx.invoked_subcommand:
        uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104


@server_manager.command("generate")
@click.argument("username")
@click.argument("password")
def generate_user(username, password):
    create_user(username, password)
