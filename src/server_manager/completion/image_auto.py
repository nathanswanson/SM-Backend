from __future__ import annotations

from typing import override

from click import Context, Parameter, ParamType
from click.shell_completion import CompletionItem

from server_manager.common.api.docker_image_api import docker_list_images


class ImageAutoType(ParamType):
    name = "image_auto"

    @override
    def shell_complete(self, ctx: Context, param: Parameter, incomplete: str) -> list[CompletionItem]:
        return [CompletionItem(name) for name in docker_list_images()]
