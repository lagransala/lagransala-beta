import re

from pydantic import HttpUrl


def http_url_key(url: HttpUrl) -> str:
    url_str = str(url)
    key = re.sub(r"https?://", "", url_str)
    return key
