from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import server_manager
from server_manager.common.singleton import SingletonMeta

default_template_path = Path(os.path.join(os.path.abspath(os.path.dirname(server_manager.__file__))), "templates")


@dataclass
class Template:
    """Represents a server template."""

    name: str
    description: str
    image: str
    env: list[str | dict[str, str]]


class TemplateManager(metaclass=SingletonMeta):
    _templates: dict[str, Template]

    def __init__(self, template_path: Path = default_template_path):
        self.template_path = template_path
        # if templates folder doesn't exist create it
        self.template_path.mkdir(parents=True, exist_ok=True)
        self.load_templates()

    def load_templates(self):
        self._templates = {}
        # Load templates from the template path
        for template_file in self.template_path.glob("*.json"):
            with open(template_file) as f:
                template_data = json.load(f)
                template = Template(**template_data)
                self._templates[template.name] = template

    def get_template(self, name: str) -> Template | None:
        return self._templates.get(name)

    def get_template_env(self, from_template: str | Template) -> dict[str, str] | None:
        if isinstance(from_template, str):
            template = self.get_template(from_template)
        elif isinstance(from_template, Template):
            template = from_template
        else:
            return None
        env_ret: dict[str, str] = {}
        if template:
            for item in template.env:
                if isinstance(item, dict):
                    # size of one and add two env_ret
                    env_ret.update(item)
                else:
                    env_ret[item] = ""
        else:
            return None
        return env_ret

    def get_templates(self) -> dict[str, Template]:
        return self._templates

    def get_template_path(self, name: str) -> str:
        return os.path.join(self.template_path, f"{name}.json")

    def create_template(self, name: str, description: str, image: str, env: dict[str, str]) -> Template:
        """Create a new template and add it to the manager."""
        if name in self._templates:
            msg = f"Template with name '{name}' already exists."
            raise ValueError(msg)
        # rebundle env from dictionary to array of one size objects
        env_list: list[str | dict[str, str]] = [{k: v} for k, v in env.items()]
        template = Template(name=name, description=description, image=image, env=env_list)
        self._templates[name] = template
        # write template to file
        template_file = self.template_path / f"{name}.json"
        with open(template_file, "w") as f:
            json.dump(template.__dict__, f, indent=4)
        return template
