from fastapi import APIRouter, HTTPException

from server_manager.webservice.db_models import Templates
from server_manager.webservice.models import StringListResponse
from server_manager.webservice.util.data_access import DB
from server_manager.webservice.util.util import expand_api_url

template = APIRouter(tags=["template"])


@template.get(expand_api_url("list"), response_model=StringListResponse)
def list_templates():
    return StringListResponse(values=list(DB().get_template_name_list()))


@template.get(expand_api_url("{name}"), response_model=Templates)
def get_template_name(name: str):
    template = DB().get_template_by_name(name)
    if template:
        return template
    raise HTTPException(status_code=404, detail="Template not found")


@template.post(expand_api_url("create"))
def add_template(template: Templates):
    ret = DB().create_template(template)
    return ret is not None


@template.post(expand_api_url("{name}/delete"))
def delete_template(name: str):
    return DB().delete_template(name)
