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
    np_m = m
    if not isinstance(m, np.ndarray):
        np_m = m.numpy()
    return hashlib.sha256(np_m.data.tobytes()).hexdigest()


def hash_user_id(
    user_id: str, assignment_id: typing.Optional[typing.Union[int, str]] = None
) -> str:
    uid = user_id
    if isinstance(user_id, bytes):
        uid = user_id.decode("utf-8")
    hash_key = "" if not assignment_id else str(assignment_id)
    hash_key += f":{uid}"
    return str(hashlib.md5(hash_key.encode("utf-8")).hexdigest())


def slash_join(*args: str) -> str:
    return reduce(urljoin, args).rstrip("/")


def get_session_id(
    assignment_id: typing.Union[int, str], user_token: typing.Union[int, str]
) -> str:
    return f"session:{assignment_id}:{user_token}"


def interpolate_accuracy(acc: float, min: float = 0.0, max: float = 1.0) -> float:
    if min >= acc:
        return 0
    if max <= acc:
        return 1.0
    return (acc - min) / (max - min)


class Datetime(datetime.datetime):
    """Use this for mocking"""

    pass


class MIME:
    json = {"Content-Type": "application/json"}
    html = {"Content-Type": "text/html"}


MIMEType = typing.Dict[str, str]
