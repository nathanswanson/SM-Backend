"""
template_api.py

Template API for managing container templates

Author: Nathan Swanson
"""

from fastapi import APIRouter, HTTPException

from server_manager.webservice.db_models import Templates
from server_manager.webservice.models import StringListResponse
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.util import expand_api_url

template = APIRouter(tags=["template"])


@template.get(expand_api_url("list"), response_model=StringListResponse)
def list_templates():
    """list all template names"""
    return StringListResponse(values=list(DB().get_template_name_list()))


@template.get(expand_api_url("{name}"), response_model=Templates)
def get_template_name(name: str):
    """get a template by name"""
    template = DB().get_template_by_name(name)
    if template:
        return template
    raise HTTPException(status_code=404, detail="Template not found")


@template.post(expand_api_url("create"))
def add_template(template: Templates):
    """add a new template"""
    ret = DB().create_template(template)
    return ret is not None


@template.post(expand_api_url("{name}/delete"))
def delete_template(name: str):
    """delete a template by name"""
    return DB().delete_template(name)
