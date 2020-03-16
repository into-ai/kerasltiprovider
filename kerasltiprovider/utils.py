import datetime
import hashlib
import typing
from functools import reduce
from urllib.parse import urljoin

import numpy as np


def hash_matrix(m: np.ndarray) -> str:
    """Hash a numpy matrix to obtain a stable key for fast indexed access

        Note: hashlib is used because the builtin python hash() function is not
        cryptographically stable across invocations
    """
    return hashlib.sha256(m.data.tobytes()).hexdigest()


def slash_join(*args: str) -> str:
    return reduce(urljoin, args).rstrip("/")


class Datetime(datetime.datetime):
    """Use this for mocking"""

    pass


class MIME:
    json = {"Content-Type": "application/json"}
    html = {"Content-Type": "text/html"}


MIMEType = typing.Dict[str, str]
