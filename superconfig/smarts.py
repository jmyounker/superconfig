"""Perform specific actions for specific keys."""

import os
import re
import time
from typing import Any, Tuple
from typing import AnyStr
from typing import Iterable
from typing import Optional
from typing import Tuple

from . import config


class SmartLayer(config.Layer):
    """Attache"""
    def __init__(self, getters=None):
        if getters is None:
            getters = {}
        self.getters = getters

    def __setitem__(self, key, getter):
        self.getters[key] = getter

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> Tuple[int, int, Optional[Any]]:
        indexes = key.split('.')
        for i in range(1, len(indexes)+1):
            k = ".".join(indexes[0:i])
            if k not in self.getters:
                continue
            found, cont, v = self.getters[k].read(k, indexes[i:len(indexes)], context, lower_layer)
            if found == config.ReadResult.Found:
                return found, cont, v
            elif cont == config.Continue.Stop:
                return found, cont, v
            elif cont == config.Continue.NextLayer:
                return found, config.Continue.Go, v
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
    def __init__(self, f, getter: Getter):
        self.f = f
        self.getter = getter

    def read(self, key, res, context, lower_layer):
        found, cont, v = self.getter.read(key, res, context, lower_layer)
        if found == config.ReadResult.NotFound:
            return found, cont, v
        # noinspection PyBroadException
        try:
            return found, cont, self.f(v)
        except Exception as e:
            raise config.ValueTransformException(key, v, e)


class Constant(Getter):
    """Always returns the assigned constant."""
    def __init__(self, c: Any):
        self.c = c

    def read(self, key, res, context, lower_layer):
        return config.ReadResult.Found, config.Continue.Go, self.c


class NotFound(Getter):
    """Simulates not found item. Exists for testing."""
    @classmethod
    def read(cls, key, res, context, lower_layer):
        return config.ReadResult.NotFound, config.Continue.Go, None


class Stop(Getter):
    """Halts all processing.

    Putting this at the bottom of a GetterStack causes the stack
    to act like a leaf node. Anything further down the tree will
    be skipped and not found will immediately result.

    """
    @classmethod
    def read(cls, key, res, context, lower_layer):
        return config.ReadResult.NotFound, config.Continue.Stop, None


class IgnoreTransformErrors(Getter):
    """Turns getter's transform errors into NotFound"""
    def __init__(self, getter):
        self.getter = getter

    def read(self, key, res, context, lower_layer):
        try:
            return self.getter.read(key, res, context, lower_layer)
        except config.ValueTransformException:
            return config.ReadResult.NotFound, config.Continue.Go, None


class Counter(Getter):
    """Counts up from n."""
    def __init__(self, n=0):
        self.n = n

    def read(self, key, res, context, lower_layer):
        self.n += 1
        return config.ReadResult.Found, config.Continue.Go, self.n


class KeyExpansionLayer(config.Layer):

    expansions_ptrn = re.compile(r"\{([^}]+)}")

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> Tuple[int, int, Optional[Any]]:
        expansions = set(self.expansions_ptrn.findall(key))
        replacements = []
        for exp in expansions:
            found, cont, v = lower_layer.get_item(exp, context, config.NullLayer)
            if found == config.ReadResult.NotFound:
                return found, config.Continue.Stop, v
            replacements.append(('{%s}' % exp, v))
        ke = key
        for exp, v in replacements:
            ke = ke.replace(exp, v)
        return lower_layer.get_item(ke, context, config.NullLayer)


class Graft(Getter):
    def __init__(self, layer):
        self.layer = layer

    def read(self, key, rest, context, lower_layer):
        found, cont, v = self.layer.get_item('.'.join(rest), context, lower_layer)
        if found == config.ReadResult.NotFound:
            return found, config.Continue.NextLayer, v
        elif cont == config.Continue.Go:
            return found, config.Continue.NextLayer, v
        else:
            return found, cont, v


class CacheLayer:
    def __init__(self, timeout_s=5):
        self.cache = {}
        self.timeout_s = timeout_s

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> tuple[int, int, Any | None]:
        now = time.time()
        resp, invalid_at = self.cache.get(key, ((config.ReadResult.NotFound, config.Continue.Go, None), now))
        if invalid_at > now:
            return resp
        resp = lower_layer.get_item(key, context, config.NullLayer())
        self.cache[key] = (resp, now + self.timeout_s)
        return resp


class LayerLoadError(Exception):
    pass


class LayerLoader:
    def __init__(
            self,
            layer_constructor,
            filename,
            check_period_s=10,
            failed_retry_period_s=5,
            clear_on_not_found=False
    ):
        self.layer_constructor = layer_constructor
        self.filename = filename
        self.check_interval_s = check_period_s
        self.failed_retry_interval_s = failed_retry_period_s
        self.layer = config.NullLayer
        self.next_refresh_time = 0
        self.last_successful_load_time = 0
        self.last_mtime = 0
        self.clear_on_not_found = clear_on_not_found

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> Tuple[int, int, Any | None]:
        now = time.time()
        if self.next_refresh_time > now:
            return self.layer.get_item(key, context, lower_layer)
        try:
            s = os.stat(self.filename)
            if s.st_mtime <= self.last_mtime:
                return self.layer.get_item(key, context, lower_layer)
            with open(self.filename, 'rb') as f:
                self.layer = self.layer_constructor(f)
            self.last_successful_load_time = now
            self.last_mtime = s.st_mtime
            self.next_refresh_time = now + self.check_interval_s
            return self.layer.get_item(key, context, lower_layer)
        except FileNotFoundError:
            if self.clear_on_not_found:
                self.layer = config.NullLayer
                self.next_refresh_time = now + self.failed_retry_interval_s
            return self.layer.get_item(key, context, lower_layer)
        except Exception:
            self.next_refresh_time = now + self.failed_retry_interval_s
            return self.layer.get_item(key, context, lower_layer)
