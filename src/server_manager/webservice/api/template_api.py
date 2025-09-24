"""
template_api.py

Template API for managing container templates

Author: Nathan Swanson
"""

from fastapi import APIRouter, HTTPException

from server_manager.webservice.db_models import Templates
from server_manager.webservice.models import (
    TemplateCreateResponse,
    TemplateDeleteRequest,
    TemplateDeleteResponse,
    TemplateListResponse,
)
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.util import expand_api_url

template = APIRouter(tags=["template"])


@template.get(expand_api_url("list"), response_model=TemplateListResponse)
def list_templates():
    """list all template names"""
    return TemplateListResponse(items=list(DB().get_template_name_list()))


@template.get(expand_api_url("{name}"), response_model=Templates)
def get_template_name(name: str):
    """get a template by name"""
    template = DB().get_template_by_name(name)
    if template:
        return template
    raise HTTPException(status_code=404, detail="Template not found")


@template.post(expand_api_url("create"), response_model=TemplateCreateResponse)
def add_template(template: Templates):
    """add a new template"""
    ret = DB().create_template(template)
    return TemplateCreateResponse(success=ret is not None)


@template.post(expand_api_url("{name}/delete"), response_model=TemplateDeleteResponse)
def delete_template(template_delete_request: TemplateDeleteRequest):
    """delete a template by name"""
    return TemplateDeleteResponse(success=DB().delete_template(template_delete_request.item))
