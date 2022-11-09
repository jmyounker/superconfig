"""Configuration library."""
from typing import Any
from typing import AnyStr
from typing import Optional
from typing import Tuple


class ValueTransformException(Exception):
    """Propagates an error generated while manipulating a retrieve value.

    Propagates an error resulting from an exception while transforming a value
    from one form to another.
    """
    def __init__(self, key, raw_value, exception, *args):
        super(self.__class__, self).__init__(*args)
        self.key = key
        self.raw_value = raw_value
        self.exception = exception


class ReadResult:
    NotFound = 0  # Not found, continue search
    Found = 1  # Found, do not continue search


class Continue:
    Stop = 0  # Terminate
    Go = 1  # Continue
    NextLayer = 2  # Continue in th next layer


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
        status, cont, value = self._get_item(key, self.context, NullLayer)
        if status == ReadResult.Found:
            return value
        elif status == ReadResult.NotFound:
            raise KeyError("key {} not found".format(key))
        else:
            raise Exception("Unknown status {} found for key {}".format(status, value))

    def get(self, key: AnyStr, default: Optional[Any] = None) -> Optional[Any]:
        status, cont, value = self._get_item(key, self.context, NullLayer)
        if status == ReadResult.Found:
            return value
        elif status == ReadResult.NotFound:
            return default
        else:
            raise Exception("Unknown status {} found for key {}".format(status, value))

    def _get_item(self, *args, **kwargs):
        try:
            return self.layer.get_item(*args, **kwargs)
        except ValueTransformException as e:
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
        return ReadResult.Found, Continue.Go, self.value

    @classmethod
    def from_file_as_string(cls, f, encoding='utf8'):
        return cls(f.read().decode(encoding))

    @classmethod
    def from_file_as_bytes(cls, f):
        return cls(f.read())
