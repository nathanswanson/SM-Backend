"""
template_api.py

Template API for managing container templates

Author: Nathan Swanson
"""

from fastapi import APIRouter, HTTPException

from server_manager.webservice.db_models import TemplatesBase, TemplatesRead
from server_manager.webservice.models import (
    TemplateCreateResponse,
    TemplateDeleteResponse,
)
from server_manager.webservice.util.data_access import DB

router = APIRouter()


@router.post("/", response_model=TemplateCreateResponse)
def add_template(template: TemplatesBase):
    """add a new template"""
    ret = DB().create_template(template)
    return TemplateCreateResponse(success=ret is not None)


@router.get("/{template_id}", response_model=TemplatesRead)
def get_template(template_id: int):
    """get a template by id"""
    template = DB().get_template(template_id)
    if template:
        return template
    raise HTTPException(status_code=404, detail="Template not found")



@router.delete("/{name}/delete", response_model=TemplateDeleteResponse)
def delete_template(template_id: int):
    """delete a template by name"""
    return TemplateDeleteResponse(success=DB().delete_template(template_id))
