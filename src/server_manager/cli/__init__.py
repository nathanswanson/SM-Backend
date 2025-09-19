# SPDX-FileCopyrightText: 2025-present NS <nathanswanson370@gmail.com>
#
# SPDX-License-Identifier: MIT
from __future__ import annotations

import click
import uvicorn
from rich.console import Console

from server_manager.__about__ import __version__
from server_manager.webservice.webservice import app

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="server_manager")
def server_manager():
    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104
