import json
from typing import AnyStr
from typing import Tuple
from typing import Optional
from typing import Any

from . import config


class JsonLayer(config.Layer):
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


class InnerJsonLayer(config.Layer):
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
