import re


def url_as_slug(url: str) -> str:
    pattern = r"\/([a-zA-Z0-9-_]*)$"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return url
