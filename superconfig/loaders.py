import contextlib
import io
import os
import time

import boto3

import config

from typing import Any
from typing import Tuple

import converters
import helpers


class AutoRefreshGetter:
    """Reloads layers when the data source changes.

    Uses a Loader to fetch a file from a remote source, and then
    creates a Layer from the file using a layer_factory.

    Every refresh_interval_s it looks for changes. If a fetch or
    layer load fails then it retries/checks every retry_interval_s.

    It can be configured to either use stale data or dump all data
    in response to clear_on_fetch_failure or clear_on_load_failure.

    If data is dumped, then all calls with return as not found.

    """
    def __init__(
            self,
            layer_constructor,
            fetcher,
            refresh_interval_s=60,
            retry_interval_s=10,
            clear_on_removal=True,
            clear_on_fetch_failure=False,
            clear_on_load_failure=False,
            is_enabled=None
    ):
        self.layer_constructor = layer_constructor
        self.fetcher = fetcher
        self.loaded_layer = config.NullLayer
        self.refresh_interval_s = refresh_interval_s
        self.retry_interval_s = retry_interval_s
        self.next_load_s = 0
        self.last_successful_load = 0
        self.clear_on_removal = clear_on_removal
        self.clear_on_fetch_failure = clear_on_fetch_failure
        self.clear_on_load_failure = clear_on_load_failure
        self.is_enabled = is_enabled or self.always_enabled

    def read(self, key, rest, context, lower_layer):
        now = time.time()
        if self.next_load_s >= now:
            return self.loaded_layer.get_item(".".join(rest), context, lower_layer)
        try:
            if not self.fetcher.load_required(now, key, rest, context, lower_layer):
                return self.loaded_layer.get_item(".".join(rest), context, lower_layer)
            if self.is_enabled(key, rest, context, lower_layer):
                with self.fetcher.load(now, key, rest, context, lower_layer) as f:
                    self.loaded_layer = self.layer_constructor(f)
                self.last_successful_load = now
                self.next_load_s += now + self.refresh_interval_s
        except DataSourceMissing:
            if self.clear_on_removal:
                self.loaded_layer = config.NullLayer
            self.next_load_s = now + self.retry_interval_s
        except FetchFailure:
            if self.clear_on_fetch_failure:
                self.loaded_layer = config.NullLayer
            self.next_load_s += now + self.retry_interval_s
        except converters.LoadFailure:
            if self.clear_on_load_failure:
                self.loaded_layer = config.NullLayer
            self.next_load_s += now + self.retry_interval_s
        return self.loaded_layer.get_item(".".join(rest), context, lower_layer)

    @staticmethod
    def always_enabled(key, rest, context, lower_layer):
        return True


class DataSourceMissing(Exception):
    pass


class FetchFailure(Exception):
    pass


class AbstractFetcher:
    """Fetchers obtain read-only binary file objects from external sources."""
    def is_enabled(self, key, rest, context, lower_layer):
        return True

    def load_required(self, now, key, rest, context, lower_layer):
        raise NotImplementedError

    @contextlib.contextmanager
    def load(self, now, key, rest, context, lower_layer):
        raise NotImplementedError


class SecretsManagerFetcher(AbstractFetcher):
    def __init__(self, name=None, client=None, stage=None):
        self._client = client
        self._name = None if name is None else helpers.ExpandableString(name)
        self._stage = stage

    def load_required(self, now, key, rest, context, lower_layer):
        return True

    @contextlib.contextmanager
    def load(self, now, key, rest, context, lower_layer):
        try:
            yield io.BytesIO(self.value_from_secret(
                self.get_secret(
                    self.get_client(),
                    self.name(key, context, lower_layer),
                    self.stage())))
        except Exception as e:
            raise FetchFailure()

    def get_client(self):
        if self._client:
            return self._client
        return boto3.client("secretsmanager")

    def name(self, key, context, lower_layer):
        if self._name is None:
            return key
        return self._name.expand(context, lower_layer)

    def stage(self):
        return self._stage

    @staticmethod
    def get_secret(client, name, stage):
        kwargs = {'SecretId': name}
        if stage is not None:
            kwargs['VersionStage'] = stage
        try:
            return client.get_secret_value(**kwargs)
        except Exception as e:
            raise FetchFailure()

    @staticmethod
    def value_from_secret(secret):
        if 'SecretString' in secret:
            return bytes(secret['SecretString'].encode('utf8'))
        elif 'SecretBinary' in secret:
            return secret['SecretBinary']
        else:
            raise FetchFailure("cannot extract value: neither SecretString nor SecretBinary found")


class FileFetcher(AbstractFetcher):
    def __init__(self, filename_tmpl):
        self.name = helpers.ExpandableString(filename_tmpl)
        self.filename = None
        self.last_mtime = 0

    def load_required(self, now, key, rest, context, lower_layer):
        # The expansion works because there is an implicit sequencing between
        # these two calls.
        filename = self.name.expand(context, lower_layer)
        if filename is None:
            raise FetchFailure()
        self.filename = filename
        if not self.last_mtime:
            return True
        try:
            return os.stat(self.filename).st_mtime > self.last_mtime
        except FileNotFoundError:
            raise DataSourceMissing()

    @contextlib.contextmanager
    def load(self, now, key, rest, context, lower_layer):
        try:
            # Get stat before, so if the file is updated after the stat, then it will
            # be found as out-of-date on the next load.
            s = os.stat(self.filename)
            with open(self.filename, 'rb') as f:
                yield f
            self.last_mtime = s.st_mtime
        except FileNotFoundError:
            raise DataSourceMissing()
        except IOError:
            raise FetchFailure()


class FileLayerLoader:
    def __init__(
            self,
            layer_constructor,
            filename,
            refresh_interval_s=10,
            retry_interval_s=5,
            is_enabled=None,
            clear_on_removal=False,
            clear_on_fetch_failure=False,
            clear_on_load_failure=False,
    ):
        self.layer_constructor = layer_constructor
        self.auto_loader = AutoRefreshGetter(
            layer_constructor=layer_constructor,
            fetcher=FileFetcher(filename),
            refresh_interval_s=refresh_interval_s,
            retry_interval_s=retry_interval_s,
            is_enabled=is_enabled,
            clear_on_removal=clear_on_removal,
            clear_on_fetch_failure=clear_on_fetch_failure,
            clear_on_load_failure=clear_on_load_failure,
        )

    def get_item(self, key, context, lower_layer: config.Layer) -> Tuple[int, int, Any | None]:
        return self.auto_loader.read("", key.split("."), context, lower_layer)


def config_switch(enable_key, default=False):
    def _config_switch(key, rest, context, lower_layer, enable_key=enable_key, default=default):
        resp = lower_layer.get_item(enable_key, context, config.NullLayer)
        if resp.is_found:
            return bool(resp.value)
        else:
            return default
    return _config_switch


class AwsParameterStoreFetcher(AbstractFetcher):
    """Pulls parameters from AWS parameterstore.

    Parameter Store has options for the kind of data stored, and how it is
    looked up.

    It seems that parameter stores are treated as trees now, and each node
    contains a single value rather than sets of values.

    It's quite possible that this design is wrong. Instead I should have
    an entire layer that caches each parameter independently, and then
    makes it looks like a normal graft.

    Value parsing then happens with transformers in a higher layer, or within
    a smart layer above the parameter store within the graft.  Actually, thinking
    about it, I can probably rely on a cache layer to handle loading since I'm
    pulling key-by-key.

    That means I don't even need to use fetchers since the fields map
    directly to the cache layer.

    """
    def __init__(self, root=None, client=None):
        self._client = client
        self._root = None if root is None else helpers.ExpandableString(root)

    def load_required(self, now, key, rest, context, lower_layer):
        return True

    @contextlib.contextmanager
    def load(self, now, key, rest, context, lower_layer):
        yield self.parameter_tree(self.get_client(), self.name(key, context, lower_layer))

    def get_client(self):
        if self._client:
            return self._client
        return boto3.client("ssm")

    def name(self, key, context, lower_layer):
        if self._root is None:
            return "/" + "/".join(key.split("."))
        return self._root.expand(context, lower_layer)

    def parameter_tree(self, client, path):
        tree = {}
        for k, p in self.describe_parameters_with_keys(client, path):
            tree[k] = ParameterNode(client, p)
        return tree

    def describe_parameters_with_keys(self, client, path):
        for p in self.describe_parameters(client, path):
            key = p["Name"][len(path):].strip("/").replace("/", ".")
            yield (key, p)

    @staticmethod
    def describe_parameters(client, path):
        paginator = client.get_paginator('describe_parameters')
        pager = paginator.paginate(
            ParameterFilters=[
                dict(Key="Path", Option="Recursive", Values=[path])
            ]
        )
        for page in pager:
            for p in page['Parameters']:
                yield p


class ParameterNode:
    def __init__(self, client, parameter):
        self.client = client
        self.parameter = parameter

    def read(self, key, rest, context, lower_layer):
        # noinspection PyBroadException
        try:
            resp = self.client.get_parameter(Name=self.parameter["Name"])
            p = resp["Parameter"]
        except Exception:
            return config.Response.not_found_next
        print(p)
        if p["Type"] == "String":
            return config.Response.found_next(p["Value"])
        elif p["Type"] == "StringList":
            return config.Response.found_next(p["Value"].split(","))
        elif p["Type"] == "SecureString":
            return config.Response.found_next(p["Value"])
        else:
            return config.Response.not_found_next
