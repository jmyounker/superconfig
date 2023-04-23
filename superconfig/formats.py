import os
from typing import AnyStr
from typing import List

import aenum

from superconfig import converters
from superconfig import statics


@aenum.unique
class Format(aenum.Enum):
    pass


def register_format(x):
    aenum.extend_enum(Format, x, x.lower())


layer_constructor_by_format = {}


def register_layer_constructor(format: Format, layer_constructor) -> None:
    layer_constructor_by_format[format.value] = layer_constructor


format_by_suffix = {}


def register_file_formats(format: Format, suffixes: List[AnyStr]) -> None:
    for suffix in suffixes:
        format_by_suffix[suffix] = format


def layer_constructor_for_filename(filename):
    _, suffix = os.path.splitext(filename)
    if suffix not in format_by_suffix:
        raise KeyError("suffix %r not known" % suffix)
    return layer_constructor_by_format[format_by_suffix[suffix].value]


def layer_constructor_for_format(format):
    return layer_constructor_by_format[format.value]


register_format("Properties")
register_layer_constructor(
    Format.Properties,
    lambda x: statics.PropertiesLayer.from_string(converters.string_from_bytes(x, encoding='utf8'))
)
register_file_formats(Format.Properties, [".prop", ".props", ".properties"])

register_format("Ini")
register_layer_constructor(
    Format.Ini,
    lambda x: statics.IniLayer.from_string(converters.string_from_bytes(x, encoding='utf8'))
)
register_file_formats(Format.Ini, [".ini"])

register_format("Json")
register_layer_constructor(
    Format.Json,
    lambda x: statics.ObjLayer(
        converters.obj_from_json(converters.string_from_bytes(x, encoding='utf8')))
)
register_file_formats(Format.Json, [".json"])

register_format("Toml")
register_layer_constructor(
    Format.Toml,
    lambda x: statics.ObjLayer(
        converters.obj_from_toml(converters.string_from_bytes(x, encoding='utf8')))
)
register_file_formats(Format.Toml, [".toml"])

register_format("Yaml")
register_layer_constructor(
    Format.Yaml,
    lambda x: statics.ObjLayer(
        converters.obj_from_yaml(converters.string_from_bytes(x, encoding='utf8')))
)
register_file_formats(Format.Yaml, [".yaml", ".yml"])



