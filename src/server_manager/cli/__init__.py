# SPDX-FileCopyrightText: 2025-present NS <nathanswanson370@gmail.com>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import click
from rich.console import Console

from server_manager.__about__ import __version__
from server_manager.webservice.webservice import web_server_start

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="server_manager")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind address for the webserver")
@click.option("--port", default=8000, show_default=True, help="Port for the webserver")
@click.option("--dev", is_flag=True, default=False, show_default=True, help="Run in development mode")
def server_manager(host, port, dev):
    web_server_start(host, port, dev)
