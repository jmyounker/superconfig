"""Configuration library."""

import contextlib
from typing import Any
from typing import AnyStr
from typing import NamedTuple
from typing import Optional

from superconfig import exceptions


class Response(NamedTuple):
    is_found: bool
    must_stop: bool
    go_next_layer: bool
    value: Optional[Any]
    expire: Optional[int]

    @classmethod
    def found(cls, value, expire=None):
        return cls(
            is_found=True,
            must_stop=False,
            go_next_layer=False,
            value=value,
            expire=expire,
        )

    @classmethod
    def found_next(cls, value, expire=None):
        return cls(
            is_found=True,
            must_stop=False,
            go_next_layer=True,
            value=value,
            expire=expire,
        )

    def new_value(self, x):
        return Response(
            is_found=self.is_found,
            must_stop=self.must_stop,
            go_next_layer=self.go_next_layer,
            value=x,
            expire=self.expire
        )

    def has_expired(self, now):
        return self.expire is None or self.expire <= now

    def still_unexpired(self, now):
        return self.expire is not None and self.expire > now

    def cache_until(self, expire):
        return Response(
            is_found=self.is_found,
            must_stop=self.must_stop,
            go_next_layer=self.go_next_layer,
            value=self.value,
            expire=expire,
        )

Response.not_found = Response(
    is_found=False,
    must_stop=False,
    go_next_layer=False,
    value=None,
    expire=None,
)


Response.not_found_stop = Response(
    is_found=False,
    must_stop=True,
    go_next_layer=False,
    value=None,
    expire=None,
)

Response.not_found_next = Response(
    is_found=False,
    must_stop=False,
    go_next_layer=True,
    value=None,
    expire=None,
)


class Context:
    """State which is passed between levels.

    Allows separation between Config logic and layer state."""

    def __init__(self):
        self._globs = []

    @property
    def globs(self):
        if not self._globs:
            return {}
        return self._globs[-1]

    @contextlib.contextmanager
    def and_globs(self, g):
        self._globs.append(g)
        yield self
        self._globs.pop()



class Layer:
    def get_item(self, key: AnyStr, context: Context, lower_layer) -> Response:
        raise NotImplemented()


class Config:
    def __init__(self, context: Context, layer=None):
        self.context = context
        self.layer = layer

    def __getitem__(self, key: AnyStr) -> Optional[Any]:
        resp = self._get_item(key, self.context, NullLayer)
        if resp.is_found:
            return resp.value
        else:
            raise KeyError("key {} not found".format(key))

    def get(self, key: AnyStr, default: Optional[Any] = None) -> Optional[Any]:
        resp = self._get_item(key, self.context, NullLayer)
        if resp.is_found:
            return resp.value
        else:
            return default

    def _get_item(self, *args, **kwargs):
        try:
            return self.layer.get_item(*args, **kwargs)
        except exceptions.ValueTransformException as e:
            raise ValueError(
                "could not parse value %s for key %s: %s",
                e.raw_value,
                e.key,
                str(e.exception))


def layered_config(context, layers=None):
    return Config(context, layer_stack(layers or []))


def layer_stack(layers):
    stack = LayerCake()
    for layer in reversed(layers):
        stack.push(layer)
    return stack


class LayerCake(Layer):
    def __init__(self):
        self.layers = TerminalLayer

    def push(self, layer):
        self.layers = LinkedLayer(layer, self.layers)

    def get_item(self, key: AnyStr, context: Context, lower_layer) -> Response:
        return self.layers.get_item(key, context, lower_layer)


class LinkedLayer(Layer):
    def __init__(self, layer, sublayer):
        self.layer = layer
        self.sublayer = sublayer

    def get_item(self, key: AnyStr, context: Context, lower_layer) -> Response:
        resp = self.layer.get_item(key, context, self.sublayer)
        if resp.is_found or resp.must_stop:
            return resp
        return self.sublayer.get_item(key, context, lower_layer)


class IndexLayer:
    def __init__(self, map):
        self.map = map

    def get_item(self, key, context, lower_layer):
        if not key:
            key = "."
        if key not in self.map:
            return Response.not_found_next
        return Response.found(self.map[key])


class TerminalLayer(Layer):
    @classmethod
    def get_item(cls, key: AnyStr, context: Context, lower_layer) -> Response:
        return lower_layer.get_item(key, context, NullLayer)


class NullLayer(Layer):
    @classmethod
    def get_item(cls, key, context, lower_layer):
        return Response.not_found


class ConstantLayer(Layer):
    """Any key returns a constant value.

    This is used in combination with Grafts to produce a single value.
    It's also useful when combined with LoadedLayers. You could produce
    the same effect by a SmartLayer with a ConstantGetter stored the
    root.

    """
    def __init__(self, value):
        self.value = value

    def get_item(self, key, context, lower_layer):
        return Response.found(self.value)

