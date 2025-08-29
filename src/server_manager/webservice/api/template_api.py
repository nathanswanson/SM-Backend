from fastapi import APIRouter, HTTPException

from server_manager.webservice.models import SuccessResponse, Template, TemplateListResponse
from server_manager.webservice.template_loader import (
    delete_template_file,
    get_template,
    get_template_names,
    save_template_to_file,
)
from server_manager.webservice.util.util import expand_api_url

template = APIRouter(tags=["template"])


@template.get(expand_api_url("list"), response_model=TemplateListResponse)
def list_templates():
    return TemplateListResponse(template=list(get_template_names()))


@template.get(expand_api_url("{name}"), response_model=Template)
def get_template_name(name: str):
    template = get_template(name)
    if template:
        return template
    raise HTTPException(status_code=404, detail="Template not found")


@template.post(expand_api_url("add_template"), response_model=SuccessResponse)
def add_template(template: Template):
    ret = save_template_to_file(template)
    return SuccessResponse(success=ret)


@template.post(expand_api_url("{name}/delete"), response_model=SuccessResponse)
def delete_template(name: str):
    ret = delete_template_file(name)
    return SuccessResponse(success=ret)
