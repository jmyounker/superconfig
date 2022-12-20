"""Perform specific actions for specific keys."""

import collections
import os
import re
import time
from typing import Any
from typing import AnyStr
from typing import Iterable
from typing import Optional
from typing import Tuple

import config
import exceptions
import helpers


class SmartLayer(config.Layer):
    """Attache"""
    def __init__(self, getters=None):
        if getters is None:
            getters = {}
        self.constant_key_getters = {}
        self.key_pattern_getters = collections.defaultdict(list)
        for key, getter in getters.items():
            self[key] = getter

    def __setitem__(self, key, getter):
        if "{}" not in key:
            self.constant_key_getters[key] = getter
        else:
            n = len(key.split("."))
            self.key_pattern_getters[n].append((re.compile("^{}$".format(key.replace("{}", r"([^.]+)"))), getter))

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> Tuple[int, int, Optional[Any]]:
        if key == "" and "" not in self.constant_key_getters:
            return config.Response.not_found
        indexes = key.split(".")
        if "" in self.constant_key_getters:
            resp = self.constant_key_getters[""].read("", indexes[0:len(indexes)], context, lower_layer)
            if resp.is_found or resp.must_stop or resp.go_next_layer:
                return resp
        for i in range(1, len(indexes)+1):
            k = ".".join(indexes[0:i])
            if k in self.constant_key_getters:
                resp = self.constant_key_getters[k].read(k, indexes[i:len(indexes)], context, lower_layer)
                if resp.is_found or resp.must_stop or resp.go_next_layer:
                    return resp
            for ptrn, getter in self.key_pattern_getters[i]:
                match = ptrn.search(k)
                if not match:
                    continue
                # Extract matches
                # Attach matches to context
                resp = getter.read(k, indexes[i:len(indexes)], context, lower_layer)
                # Pop context
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



def via(getter, key="", rest=None):
    if rest is None:
        rest = []

    # noinspection PyShadowingNames
    def f(context, lower_layer, key=key, getter=getter, rest=rest):
        return getter.read(key, rest, context, lower_layer)
    return f


def expansion(c):
    expansions = helpers.expansions(c)
    if not expansions:
        return config_value_constant_key(c)

    # noinspection PyShadowingNames
    def f(context, lower_layer, c=c, expansions=expansions):
        return helpers.expand(c, expansions, context, lower_layer)
    return f


def config_value(key):
    expansions = helpers.expansions(key)
    if not expansions:
        return config_value_constant_key(key)

    # noinspection PyShadowingNames
    def f(context, lower_layer, key=key, expansions=expansions):
        target_key = helpers.expand(key, expansions, context, lower_layer)
        resp = lower_layer.get_item(target_key, context, config.NullConfig)
        if not resp.found:
            raise KeyError()
        return resp.value
    return f


def config_value_constant_key(key):

    # noinspection PyShadowingNames
    def f(context, lower_layer, key=key):
        resp = lower_layer.get_item(key, context, config.NullLayer)
        if not resp.found:
            raise KeyError()
        return resp.value
    return f


def constant(c):
    return lambda context, lower_layer, c=c: c


def expanded(f):

    def _expansion(context, lower_layer):
        x = f(context, lower_layer)
        return helpers.expand(x, helpers.expansions(x), context, lower_layer)
    return _expansion


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
            raise exceptions.ValueTransformException(key, resp.value, e)


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
        except exceptions.ValueTransformException:
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
    def __init__(self, ttl_s=constant(5), negative_ttl_s=constant(0)):
        self.cache = {}
        self.ttl_s = ttl_s
        self.negative_ttl_s = negative_ttl_s

    def get_item(self, key: AnyStr, context: config.Context, lower_layer: config.Layer) -> config.Response:
        now = time.time()
        cached_resp = self.cache.get(key, None)
        if cached_resp is not None and cached_resp.still_unexpired(now):
            return cached_resp
        resp = lower_layer.get_item(key, context, config.NullLayer())
        if resp.is_found:
            return _cache(self.cache, key, resp, now, self.ttl_s(context, lower_layer))
        if not self.negative_ttl_s(context, lower_layer):
            return resp
        return _cache(self.cache, key, resp, now, self.negative_ttl_s(context, lower_layer))

    def _cache(self, key, resp, now, ttl_s):
        if resp.expire is None:
            cache_resp = resp.cache_until(now + ttl_s)
            self.cache[key] = cache_resp
            return cache_resp
        else:
            self.cache[key] = resp
            return resp


class CacheGetter(Getter):
    def __init__(self, getter, ttl_s=constant(5), negative_ttl_s=constant(0)):
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
        resp = self.getter.read(key, rest, context, lower_layer)
        if resp.is_found:
            return _cache(self.cache, cache_key, resp, now, self.ttl_s(constant, lower_layer))
        if not self.negative_ttl_s(context, lower_layer):
            return resp
        return _cache(self.cache, cache_key, resp, now, self.negative_ttl_s(constant, lower_layer))


class ExpansionGetter(Getter):
    def __init__(self, getter):
        self.getter = getter

    def read(self, key: AnyStr, rest: list[AnyStr], context: config.Context, lower_layer: config.Layer) -> config.Response:
        resp = self.geter(key, rest, context, lower_layer)
        if not resp.is_found:
            return resp
        expansions = helpers.expansions(resp.value)
        if not expansions:
            return resp
        return resp.new_value(helpers.expand(resp.value, expansions, context, lower_layer))


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


class BaseKeyReference(Getter):
    def read(self, key: AnyStr, rest: list[AnyStr], context: config.Context, lower_layer: config.Layer) -> config.Response:
        return lower_layer.get_item(key, context, config.NullLayer)


class FullKeyReference(Getter):
    def read(self, key: AnyStr, rest: list[AnyStr], context: config.Context, lower_layer: config.Layer) -> config.Response:
        return lower_layer.get_item(full_key(key, rest), context, config.NullLayer)


class ExpansionGetter(Getter):
    def __init__(self, getter):
        self.getter = getter

    def read(self, key: AnyStr, rest: list[AnyStr], context: config.Context, lower_layer: config.Layer) -> config.Response:
        resp = self.getter.read(key, rest, context, lower_layer)
        if not resp.found:
            return resp
        x = helpers.expand(resp.value, helpers.expansions(resp.value), context, lower_layer)
        return resp.new_value(x)


class BaseKeyGetter():
    def __init__(self, getter):
        self.getter = getter

    def read(self, key: AnyStr, rest: list[AnyStr], context: config.Context, lower_layer: config.Layer) -> config.Response:
        return self.getter.read(key, [], context, lower_layer)


class ExpandedKeyGetter():
    def __init__(self, getter):
        self.getter = getter

    def read(self, key: AnyStr, rest: list[AnyStr], context: config.Context, lower_layer: config.Layer) -> config.Response:
        expanded_key = helpers.expand(key, helpers.expansions(key), context, lower_layer)
        return self.getter.read(expanded_key, [], context, lower_layer)


class FullKeyGetter():
    def __init__(self, getter):
        self.getter = getter

    def read(self, key: AnyStr, rest: list[AnyStr], context: config.Context, lower_layer: config.Layer) -> config.Response:
        return self.getter.read(full_key(key, rest), [], context, lower_layer)

