"""Perform specific actions for specific keys."""

import os
from typing import Any
from typing import AnyStr
from typing import Iterable
from typing import Optional
from typing import Tuple

from . import config


class SmartLayer(config.Layer):
    """Attache"""
    def __init__(self):
        self.getters = {}

    def __setitem__(self, key, getter):
        self.getters[key] = getter

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> Tuple[int, int, Optional[Any]]:
        indexes = key.split('.')
        for i in range(1, len(indexes)+1):
            k = ".".join(indexes[0:i])
            if k not in self.getters:
                continue
            found, cont, v = self.getters[k].read(k, indexes[i+1:len(indexes)], context, lower_layer)
            if found == config.ReadResult.Found:
                return found, cont, v
            if cont == config.Continue.Stop:
                return found, cont, v
        return config.ReadResult.NotFound, config.Continue.Go, None


class Getter:
    """Get the value for a key at a specific point in the key search.

    Getters have access to their attachment path (the portion of the key that
    triggered the Getter. They have access to any config information, and they have
    access to layers of config beneath them.

    """
    def read(self, key: AnyStr, rest: AnyStr, context: config.Context, lower_layer: config.Layer):
        raise NotImplementedError()


class GetterStack(Getter):
    """Applies getters one after another to the same key.


    """
    def __init__(self, getters: Iterable[Getter]):
        self.getters = getters

    def read(self, key, res, context, lower_layer):
        for g in self.getters:
            found, cont, v = g.read(key, res, context, lower_layer)
            if found == config.ReadResult.Found:
                return found, cont, v
            if cont == config.Continue.Stop:
                return found, cont, v
        return config.ReadResult.NotFound, config.Continue.Go, None


class Env(Getter):
    """Gets a key from an environment variable."""
    def __init__(self, envar: AnyStr):
        self.envar = envar

    def read(self, key, rest, context, lower_layer):
        if self.envar not in os.environ:
            return config.ReadResult.NotFound, config.Continue.Go, None
        return config.ReadResult.Found, config.Continue.Go, os.environ[self.envar]


class Transform(Getter):
    """Transform wraps another getter.

    If that getter finds a value, then the transformer applies
    the function to it.  An example might be turning a dictionary
    into an object or a two element array into a complex number.

    """
    def __init__(self, getter: Getter, f):
        self.getter = getter
        self.f = f

    def read(self, key, res, context, lower_layer):
        found, cont, v = self.getter.read(key, res, context, lower_layer)
        if found == config.ReadResult.Found:
            return found, cont, self.f(v)
        return found, cont, v


class Constant(Getter):
    """Always returns the assigned constant."""
    def __init__(self, c: Any):
        self.c = c

    def read(self, key, res, context, lower_layer):
        return config.ReadResult.Found, config.Continue.Go, self.c
