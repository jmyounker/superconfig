import configparser
import json
import re
from typing import AnyStr
from typing import Tuple
from typing import Optional
from typing import Any

import jproperties

from superconfig import LoadFailure
from . import config


class ObjLayer(config.Layer):
    def __init__(self, data):
        self.data = data

    def get_item(self, key: AnyStr, context: config.Context, lower_layer) -> Tuple[int, int, Optional[Any]]:
        """Gets the value for key or (Found, Go, None) if not found on terminal node."""
        indexes = key.split('.')
        v = self.data
        for i in range(0, len(indexes)):
            if not isinstance(v, dict):
                return config.ReadResult.NotFound, config.Continue.Go, None
            index = indexes[i]
            if index not in v:
                return config.ReadResult.NotFound, config.Continue.Go, None
            v = v[index]
        # Last item must not be a dict
        if isinstance(v, dict):
            return config.ReadResult.NotFound, config.Continue.Go, None
        return config.ReadResult.Found, config.Continue.Go, v

    @classmethod
    def from_file(cls, f):
        return cls(json.load(f))


class InnerObjLayer(config.Layer):
    def __init__(self, data):
        self.data = data

    def get_item(self, key: AnyStr, context: config.Context, lower_layer) -> Tuple[int, int, Optional[Any]]:
        """Gets the value for key or (Found, Go, None) if not found on terminal node."""
        indexes = key.split('.')
        v = self.data
        for i in range(0, len(indexes)):
            if not isinstance(v, dict):
                return config.ReadResult.NotFound, config.Continue.Go, None
            index = indexes[i]
            if index not in v:
                return config.ReadResult.NotFound, config.Continue.Go, None
            v = v[index]
        return config.ReadResult.Found, config.Continue.Go, v

    @classmethod
    def from_file(cls, f):
        return cls(json.load(f))


class IniLayer(config.Layer):
    def __init__(self, config_parser: configparser.ConfigParser):
        self.config_parser = config_parser

    section_item_ptrn = re.compile(r"(.+)\.([^.]+)$")

    @classmethod
    def from_string(cls, x):
        c = configparser.ConfigParser()
        try:
            c.read_string(x)
        except Exception:
            raise LoadFailure()
        return cls(c)

    def get_item(self, key: AnyStr, context: config.Context, lower_layer) -> Tuple[int, int, Optional[Any]]:
        """Gets the value for key or (Found, Go, None) if not found on terminal node."""
        section_item = self.section_item_ptrn.match(key)
        if not section_item:
            return config.ReadResult.NotFound, config.Continue.Go, None
        section = section_item.group(1)
        item = section_item.group(2)
        try:
            return config.ReadResult.Found, config.Continue.Go, self.config_parser[section][item]
        except Exception:
            return config.ReadResult.NotFound, config.Continue.Go, None


class PropertiesLayer(config.Layer):
    def __init__(self, properties: jproperties.Properties):
        self.properties = properties

    @classmethod
    def from_string(cls, x):
        p = jproperties.Properties(x)
        try:
            p.load(x)
        except Exception:
            raise LoadFailure()
        return cls(p)

    def get_item(self, key: AnyStr, context: config.Context, lower_layer) -> Tuple[int, int, Optional[Any]]:
        """Gets the value for key or (Found, Go, None) if not found on terminal node."""
        if key not in self.properties:
            return config.ReadResult.NotFound, config.Continue.Go, None
        try:
            return config.ReadResult.Found, config.Continue.Go, self.properties[key].data
        except Exception:
            return config.ReadResult.NotFound, config.Continue.Go, None
