"""Configuration library."""

from typing import Any
from typing import AnyStr
from typing import Optional
from typing import Tuple


class ReadResult:
    NotFound = 0  # Not found, continue search
    Found = 1  # Found, do not continue search


class Continue:
    Stop = 0  # Terminate
    Go = 1  # Continue


class Context:
    """State which is passed between levels.

    Allows separation between Config logic and layer state."""
    pass


class Config:
    def __init__(self, context, layer):
        self.context = context
        self.layer = layer

    def __getitem__(self, key: AnyStr) -> Optional[Any]:
        status, cont, value = self.layer.get_item(key, self.context)
        if status == ReadResult.Found:
            return value
        elif status == ReadResult.NotFound:
            raise KeyError("key {} not found".format(key))
        else:
            raise Exception("Unknown status {} found for key {}".format(status, value))

    def get(self, key:AnyStr, default:Any=None) -> Optional[Any]:
        status, cont, value = self.layer.get_item(key, self.context)
        if status == ReadResult.Found:
            return value
        elif status == ReadResult.NotFound:
            return default
        else:
            raise Exception("Unknown status {} found for key {}".format(status, value))


class DictLayer:
    def __init__(self, data):
        self.data = data

    def get_item(self, key: AnyStr, context: Context) -> Tuple[int, int, Optional[Any]]:
        """Gets the value for key or (Found, Go, None) if not found on terminal node."""
        indexes = key.split('.')
        v = self.data
        for i in range(0, len(indexes)):
            if not isinstance(v, dict):
                return ReadResult.NotFound, Continue.Go, None
            index = indexes[i]
            if index not in v:
                return ReadResult.NotFound, Continue.Go, None
            v = v[index]
        # Last item must not be a dict
        if isinstance(v, dict):
            return ReadResult.NotFound, Continue.Go, None
        return ReadResult.Found, Continue.Go, v



class LayerCake:
    def __init__(self):
        self.layers = [NullLayer]

    def push(self, layer):
        self.layers.append(layer)

    def pop(self):
        if len(self.layers) == 1:
            raise Exception("no more layers to pop")
        self.layers = self.layers[:-2]

    def get_item(self, key: AnyStr, context: Context) -> Tuple[int, int, Optional[Any]]:
        for i in range(len(self.layers)-1, 0, -1):
            found, cont, v = self.layers[i].get_item(key, context)
            if found == ReadResult.Found:
                return found, cont, v
            if cont == Continue.Stop:
                return found, cont, v
        return ReadResult.NotFound, Continue.Go, None


class NullLayer:
    @classmethod
    def get_item(cls, key, context):
        return ReadResult.NotFound, Continue.Go, None

