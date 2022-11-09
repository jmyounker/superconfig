"""Tools for building constructors from binary files.

For example: You want to convert a base64 encoded
file into a DictLayer(). To do this you'd build this
constructor:

    c = constructor(
        DictLayer,
        obj_from_json(
            string_from_bytes(
                bytes_from_base64(
                    bytes_from_file
                )
            ),
            encoding='utf8'
        )
    )

You can use this construct with something AutoRefreshGetter
to construct a dictionary from a base64 encoded secret:




"""

import base64
import json

import binascii



class LoadFailure(Exception):
    pass


def construct(f, transform):
    return lambda x, f=f, transform=transform: f(transform(x))


def string_from_bytes(transform, encoding='utf8'):
    def _string_from_file(x, transform=transform, encoding=encoding):
        try:
            return transform(x).decode(encoding)
        except:
            raise LoadFailure()
    return _string_from_file


def bytes_from_file(x):
    return x.read()


def obj_from_json(transform):
    def _json_from_string(x, transform=transform):
        try:
            return json.loads(transform())
        except Exception:
            raise LoadFailure()
    return _json_from_string


def bytes_from_base64(transform):
    def _bytes_from_base64(x, transform=transform):
        try:
            return base64.b64decode(transform(x), validate=True)
        except binascii.Error:
            raise LoadFailure("characters outside base64")
    return _bytes_from_base64

