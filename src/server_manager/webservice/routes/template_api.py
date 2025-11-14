"""
template_api.py

Template API for managing container templates

Author: Nathan Swanson
"""

from fastapi import APIRouter, HTTPException

from server_manager.webservice.db_models import TemplatesCreate, TemplatesRead
from server_manager.webservice.docker_interface.docker_image_api import docker_image_exposed_port
from server_manager.webservice.models import (
    TemplateCreateResponse,
    TemplateDeleteResponse,
)
from server_manager.webservice.util.data_access import DB

router = APIRouter()


@router.post("/", response_model=TemplateCreateResponse)
async def add_template(template: TemplatesCreate):
    """add a new template"""
    ports = await docker_image_exposed_port(template.image)
    ret = DB().create_template(template, exposed_port=ports)
    return TemplateCreateResponse(success=ret is not None)


@router.get("/{template_id}", response_model=TemplatesRead)
def get_template(template_id: int):
    """get a template by id"""
    template = DB().get_template(template_id)
    if template:
        return template
    raise HTTPException(status_code=404, detail="Template not found")


@router.patch("/{template_id}", response_model=TemplateCreateResponse)
async def update_template(template_id: int, template: TemplatesCreate):
    """update a template by id"""
    ports = await docker_image_exposed_port(template.image)
    ret = DB().update_template(template_id, template, exposed_port=ports)
    return TemplateCreateResponse(success=ret is not None)


@router.delete("/{name}/delete", response_model=TemplateDeleteResponse)
def delete_template(template_id: int):
    """delete a template by name"""
    return TemplateDeleteResponse(success=DB().delete_template(template_id))
