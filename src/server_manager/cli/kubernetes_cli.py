import click

from server_manager.cli import server_manager
from server_manager.webservice.interface.interface_manager import get_client


@server_manager.group()
def container_if() -> None:
    """Kubernetes related commands"""


@container_if.command()
@click.argument("atribute", type=str)
@click.argument("args", nargs=-1)
async def run(atribute: str, args: tuple[str]) -> None:
    await getattr(get_client(), atribute)(args[0])
    click.echo(f"Ran {atribute} with args {args}")
