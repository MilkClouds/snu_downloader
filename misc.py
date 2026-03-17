import functools
import pathlib
import shutil

import requests
from tqdm.auto import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm


def yes_or_no(question):
    while "the answer is invalid":
        reply = str(input(question + " (y/n): ")).lower().strip()
        if len(reply) > 0:
            if reply[0] == "y":
                return True
            if reply[0] == "n":
                return False


# modified https://stackoverflow.com/a/63831344
def download(url, filename, *args, **kwargs):
    r = requests.get(url, stream=True, allow_redirects=True, *args, **kwargs)
    if r.status_code != 200:
        r.raise_for_status()  # Will only raise for 4xx codes, so...
        raise RuntimeError(f"Request to {url} returned status code {r.status_code}")
    file_size = int(r.headers.get("Content-Length", 0))

    path = pathlib.Path(filename).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    desc = "(Unknown total file size)" if file_size == 0 else ""
    r.raw.read = functools.partial(r.raw.read, decode_content=True)  # Decompress if needed
    with logging_redirect_tqdm():
        with tqdm.wrapattr(r.raw, "read", total=file_size, desc=desc) as r_raw:
            with path.open("wb") as f:
                shutil.copyfileobj(r_raw, f)

    return path
