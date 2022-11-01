"""Configuration library."""
import os
from typing import Any
from typing import AnyStr
from typing import Iterable
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


class Layer:
    def get_item(self, key: AnyStr, context: Context, lower_layer) -> Tuple[int, int, Optional[Any]]:
        raise NotImplemented()


class Config:
    def __init__(self, context: Context, layer=None):
        self.context = context
        self.layer = layer

    def __getitem__(self, key: AnyStr) -> Optional[Any]:
        status, cont, value = self.layer.get_item(key, self.context, NullLayer)
        if status == ReadResult.Found:
            return value
        elif status == ReadResult.NotFound:
            raise KeyError("key {} not found".format(key))
        else:
            raise Exception("Unknown status {} found for key {}".format(status, value))

    def get(self, key: AnyStr, default: Optional[Any] = None) -> Optional[Any]:
        status, cont, value = self.layer.get_item(key, self.context, NullLayer)
        if status == ReadResult.Found:
            return value
        elif status == ReadResult.NotFound:
            return default
        else:
            raise Exception("Unknown status {} found for key {}".format(status, value))


def layered_config(context, layers=None):
    config = Config(context, LayerCake())
    for layer in (layers or []):
        config.layer.push(layer)
    return config


class LayerCake(Layer):
    def __init__(self):
        self.layers = TerminalLayer

    def push(self, layer):
        self.layers = LinkedLayer(layer, self.layers)

    def get_item(self, key: AnyStr, context: Context, lower_layer) -> Tuple[int, int, Optional[Any]]:
        return self.layers.get_item(key, context, lower_layer)


class LinkedLayer(Layer):
    def __init__(self, layer, sublayer):
        self.layer = layer
        self.sublayer = sublayer

    def get_item(self, key: AnyStr, context: Context, lower_layer) -> Tuple[int, int, Optional[Any]]:
        found, cont, v = self.layer.get_item(key, context, self.sublayer)
        if found == ReadResult.Found:
            return found, cont, v
        if cont == Continue.Stop:
            return found, cont, v
        return self.sublayer.get_item(key, context, lower_layer)


class TerminalLayer(Layer):
    @classmethod
    def get_item(cls, key: AnyStr, context: Context, lower_layer) -> Tuple[int, int, Optional[Any]]:
        return lower_layer.get_item(key, context, NullLayer)


class NullLayer(Layer):
    @classmethod
    def get_item(cls, key, context, lower_layer):
        return ReadResult.NotFound, Continue.Go, None


class SmartLayer(Layer):
    def __init__(self):
        self.getters = {}

    def get_item(self, key: AnyStr, context: Context, lower_layer: Layer) -> Tuple[int, int, Optional[Any]]:
        indexes = key.split('.')
        for i in range(len(indexes)):
            k = ".".join(indexes[0:i])
            if k not in self.getters:
                continue
            found, cont, v = self.getters[k].read(k, indexes[i+1:len(indexes)], context, lower_layer)
            if found == ReadResult.Found:
                return found, cont, v
            if cont == Continue.Stop:
                return found, cont, v
        return ReadResult.NotFound, Continue.Go, None


class Getter:
    def read(self, key: AnyStr, rest: AnyStr, context: Context, lower_layer: Layer):
        raise NotImplementedError()


class Env(Getter):
    def __init__(self, envar: AnyStr):
        self.envar = envar

    def read(self, key, rest, context, lower_layer):
        if self.envar not in os.environ:
            return ReadResult.NotFound, Continue.Go, None
        return os.environ[self.envar]


class Transform(Getter):
    def __init__(self, getter: Getter, f):
        self.getter = getter
        self.f = f

    def read(self, key, res, context, lower_layer):
        found, cont, v = self.getter.read(key, res, context, lower_layer)
        if found == ReadResult.Found:
            return found, cont, self.f(v)
        return found, cont, v


class Constant(Getter):
    def __init__(self, c: Any):
        self.c = c

    def read(self, key, res, context, lower_layer):
        return ReadResult.Found, Continue.Go, self.c


class GetterStack(Getter):
    def __init__(self, getters: Iterable[Getter]):
        self.getters = getters

    def read(self, key, res, context, lower_layer):
        for g in self.getters:
            found, cont, v = g.read(key, res, context, lower_layer)
            if found == ReadResult.Found:
                return found, cont, v
            if cont == Continue.Stop:
                return found, cont, v
        return ReadResult.NotFound, Continue.Go, None
