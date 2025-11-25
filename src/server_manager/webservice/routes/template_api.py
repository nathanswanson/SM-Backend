"""
template_api.py

Template API for managing container templates

Author: Nathan Swanson
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from server_manager.webservice.db_models import TemplatesCreate, TemplatesRead
from server_manager.webservice.interface.docker.docker_image_api import docker_image_exposed_port
from server_manager.webservice.models import (
    TemplateCreateResponse,
    TemplateDeleteResponse,
)
from server_manager.webservice.routes.management_api import get_db
from server_manager.webservice.util.data_access import DB

router = APIRouter()


@router.post("/", response_model=TemplateCreateResponse)
async def add_template(template: TemplatesCreate, db: Annotated[DB, Depends(get_db)]):
    """add a new template"""
    ports = await docker_image_exposed_port(template.image)
    ret = db.create_template(template, exposed_port=ports)
    return TemplateCreateResponse(success=ret is not None)


@router.get("/{template_id}", response_model=TemplatesRead)
def get_template(template_id: int, db: Annotated[DB, Depends(get_db)]):
    """get a template by id"""
    template = db.get_template(template_id)
    if template:
        return template
    raise HTTPException(status_code=404, detail="Template not found")


@router.patch("/{template_id}", response_model=TemplateCreateResponse)
async def update_template(template_id: int, template: TemplatesCreate, db: Annotated[DB, Depends(get_db)]):
    """update a template by id"""
    ports = await docker_image_exposed_port(template.image)
    ret = db.update_template(template_id, template, exposed_port=ports)
    return TemplateCreateResponse(success=ret is not None)


@router.delete("/{name}/delete", response_model=TemplateDeleteResponse)
def delete_template(template_id: int, db: Annotated[DB, Depends(get_db)]):
    """delete a template by name"""
    return TemplateDeleteResponse(success=db.delete_template(template_id))
