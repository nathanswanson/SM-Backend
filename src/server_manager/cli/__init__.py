# SPDX-FileCopyrightText: 2025-present NS <nathanswanson370@gmail.com>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import importlib

import click
from rich.console import Console

from server_manager.__about__ import __version__
from server_manager.webservice.logger import LOG_CONFIG

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="server_manager")
@click.pass_context
def server_manager(ctx) -> None:
    if not ctx.invoked_subcommand:
        import uvicorn

        mod = importlib.import_module("server_manager.webservice.webservice")
        app = mod.app
        uvicorn.run(app, log_config=LOG_CONFIG, host="0.0.0.0", port=8000)


from server_manager.cli.kubernetes_cli import container_if
