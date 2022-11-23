"""Perform specific actions for specific keys."""

import os
import time
from typing import Any
from typing import AnyStr
from typing import Iterable
from typing import Optional
from typing import Tuple

from . import config
from . import helpers


class SmartLayer(config.Layer):
    """Attache"""
    def __init__(self, getters=None):
        if getters is None:
            getters = {}
        self.getters = getters

    def __setitem__(self, key, getter):
        self.getters[key] = getter

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> Tuple[int, int, Optional[Any]]:
        if key == "" and "" not in self.getters:
            return config.Response.not_found
        indexes = key.split(".")
        if "" in self.getters:
            resp = self.getters[""].read("", indexes[0:len(indexes)], context, lower_layer)
            if resp.is_found or resp.must_stop or resp.go_next_layer:
                return resp
        for i in range(1, len(indexes)+1):
            k = ".".join(indexes[0:i])
            if k not in self.getters:
                continue
            resp = self.getters[k].read(k, indexes[i:len(indexes)], context, lower_layer)
            if resp.is_found or resp.must_stop or resp.go_next_layer:
                return resp
        return config.Response.not_found


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
            resp = g.read(key, res, context, lower_layer)
            if resp.is_found or resp.must_stop:
                return resp
        return config.Response.not_found


class Env(Getter):
    """Gets a key from an environment variable."""
    def __init__(self, envar: AnyStr):
        self.envar = envar

    def read(self, key, rest, context, lower_layer):
        if self.envar not in os.environ:
            return config.Response.not_found
        return config.Response.found(os.environ[self.envar])


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
        resp = self.getter.read(key, res, context, lower_layer)
        if not resp.is_found:
            return resp
        # noinspection PyBroadException
        try:
            return resp.new_value(self.f(resp.value))
        except Exception as e:
            raise config.ValueTransformException(key, resp.value, e)


class Constant(Getter):
    """Always returns the assigned constant."""
    def __init__(self, c: Any):
        self.c = c

    def read(self, key, res, context, lower_layer):
        return config.Response.found(self.c)


class NotFound(Getter):
    """Simulates not found item. Exists for testing."""
    @classmethod
    def read(cls, key, res, context, lower_layer):
        return config.Response.not_found


class Stop(Getter):
    """Halts all processing.

    Putting this at the bottom of a GetterStack causes the stack
    to act like a leaf node. Anything further down the tree will
    be skipped and not found will immediately result.

    """
    @classmethod
    def read(cls, key, res, context, lower_layer):
        return config.Response.not_found_stop


class IgnoreTransformErrors(Getter):
    """Turns getter's transform errors into NotFound"""
    def __init__(self, getter):
        self.getter = getter

    def read(self, key, res, context, lower_layer):
        try:
            return self.getter.read(key, res, context, lower_layer)
        except config.ValueTransformException:
            return config.Response.not_found


class Counter(Getter):
    """Counts up from n."""
    def __init__(self, n=0):
        self.n = n

    def read(self, key, res, context, lower_layer):
        self.n += 1
        return config.Response.found(self.n)


class KeyExpansionLayer(config.Layer):

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> Tuple[int, int, Optional[Any]]:
        k = helpers.expand(key, helpers.expansions(key), context, lower_layer)
        if k is None:
            return config.Response.not_found
        return lower_layer.get_item(k, context, config.NullLayer)


class Graft(Getter):
    def __init__(self, layer):
        self.layer = layer

    def read(self, key, rest, context, lower_layer):
        resp = self.layer.get_item('.'.join(rest), context, lower_layer)
        if not resp.is_found or not resp.go_next_layer:
            return config.Response.found_next(resp.value)
        return resp


class CacheLayer:
    def __init__(self, ttl_s=5, negitive_ttl_s=0):
        self.cache = {}
        self.ttl_s = ttl_s
        self.negative_ttl_s = negitive_ttl_s

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> config.Response:
        now = time.time()
        cached_resp = self.cache.get(key, None)
        if cached_resp is not None and cached_resp.still_unexpired(now):
            return cached_resp
        resp = lower_layer.get_item(key, context, config.NullLayer())
        if resp.is_found:
            return _cache(self.cache, key, resp, now, self.ttl_s)
        if not self.negative_ttl_s:
            return resp
        return _cache(self.cache, key, resp, now, self.negative_ttl_s)

    def _cache(self, key, resp, now, ttl_s):
        if resp.expire is None:
            cache_resp = resp.cache_until(now + ttl_s)
            self.cache[key] = cache_resp
            return cache_resp
        else:
            self.cache[key] = resp
            return resp


class CacheGetter:
    def __init__(self, getter, ttl_s=5, negative_ttl_s=0):
        self.getter = getter
        self.cache = {}
        self.ttl_s = ttl_s
        self.negative_ttl_s = negative_ttl_s

    def read(self, key: AnyStr, rest: list[AnyStr], context: config.Context, lower_layer: config.Layer) -> config.Response:
        now = time.time()
        cache_key = full_key(key, rest)
        cached_resp = self.cache.get(cache_key, None)
        if cached_resp is not None and cached_resp.still_unexpired(now):
            return cached_resp
        resp = self.getter.read(key, rest, context, config.NullLayer())
        if resp.is_found:
            return _cache(self.cache, cache_key, resp, now, self.ttl_s)
        if not self.negative_ttl_s:
            return resp
        return _cache(self.cache, cache_key, resp, now, self.negative_ttl_s)


def _cache(cache, cache_key, resp, now, ttl_s):
    if resp.expire is None:
        cache_resp = resp.cache_until(now + ttl_s)
        cache[cache_key] = cache_resp
        return cache_resp
    else:
        cache[cache_key] = resp
        return resp


class IndexGetterLayer:
    def __init__(self, map):
        self.map = map

    def get_item(self, key, context, lower_layer):
        if key not in self.map:
            return config.Response.not_found_next
        return self.map[key].read(key, [], context, lower_layer)


class GetterAsLayer(config.Layer):
    def __init__(self, getter):
        self.getter = getter

    def get_item(self, key, context, lower_layer: config.Layer) -> config.Response:
        return self.getter.read("", key.split("."), context, lower_layer)


def full_key(key, rest):
    return "{}.{}".format(key, ".".join(rest)).strip(".")
