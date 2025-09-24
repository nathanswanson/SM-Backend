"""
util.py

Utility functions for the webservice

Author: Nathan Swanson
"""

import inspect
import os
import re


def expand_api_url(api_path: str) -> str:
    """expand an api path to include the file name as a prefix"""
    caller = inspect.currentframe()
    if caller:
        caller = getattr(caller, "f_back", None)
        caller = getattr(caller, "f_code", None)
        caller = getattr(caller, "co_filename", None)
        if caller:
            file_name = os.path.basename(caller).replace("_api.py", "")
            return f"/api/{file_name}/{api_path}"
    # raise exception
    msg = "Could not determine caller frame."
    raise RuntimeError(msg)


def url_as_slug(url: str) -> str:
    """convert a url path to a slug (last part of the path)"""
    pattern = r"\/([a-zA-Z0-9-_]*)$"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return url
