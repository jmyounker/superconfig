"""Tools for building constructors from binary files.

For example: You want to convert a base64 encoded
file into a DictLayer(). To do this you'd build this
constructor:

    c = lambda f: ObjLayer(
        obj_from_json(
            string_from_bytes(
                bytes_from_base64(f),
                encoding='utf8'
            )
        )
    )


"""

import binascii
import base64
import io
import json
from typing import Any
from typing import AnyStr

import toml

from superconfig.exceptions import LoadFailure


try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader, Dumper

import yaml


def obj_from_json(x: AnyStr) -> Any:
    try:
        return json.loads(x)
    except Exception:
        raise LoadFailure()


def obj_from_toml(x: AnyStr) -> Any:
    try:
        return toml.loads(x)
    except Exception:
        raise LoadFailure()


def obj_from_yaml(x: AnyStr) -> Any:
    try:
        return yaml.load(x, Loader=Loader)
    except Exception as e:
        raise LoadFailure(e)


def string_from_bytes(x: bytes, encoding='utf8') -> AnyStr:
    try:
        return x.decode(encoding)
    except Exception:
        raise LoadFailure()


def bytes_from_file(x: io.BytesIO) -> bytes:
    return x.read()


def bytes_from_base64(x: AnyStr) -> bytes:
    try:
        return base64.b64decode(x, validate=True)
    except binascii.Error:
        raise exceptions.LoadFailure("characters outside base64")

