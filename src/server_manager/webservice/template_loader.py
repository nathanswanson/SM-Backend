import json
import os
from functools import lru_cache

from server_manager.webservice.models import Template

default_path = os.path.expanduser("~/server_manager/resources")


@lru_cache
def get_templates() -> list[Template]:
    templates: list[Template] = []
    # TODO: make sure it uses external files instead internal like now
    for resource in os.listdir(default_path):
        if resource.endswith(".json") and resource != "template.schema.json":
            with open(os.path.join(default_path, resource)) as f:
                json_data = json.load(f)
                templates.append(Template(**json_data))
    return templates


def get_template(name: str):
    templates = get_templates()
    for template in templates:
        if template.name == name:
            return template
    return None


def get_template_names() -> list[str]:
    return [template.name for template in get_templates()]


def delete_template_file(name: str) -> bool:
    # delete from disk
    os.unlink(os.path.join(default_path, f"{name}.template.json"))
    reload_templates()
    return True


def reload_templates():
    get_templates.cache_clear()


def save_template_to_file(template: Template):
    # add template to json files
    templates = get_templates()
    templates.append(template)
    with open(os.path.join(default_path, f"{template.name}.template.json"), "w") as f:
        f.write(template.model_dump_json(indent=4))
        return True
    return False
