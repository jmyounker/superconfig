import contextlib
import io
import os
import time


import boto3

import config

from typing import Any
from typing import AnyStr
from typing import Optional
from typing import Tuple


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
            clear_on_fetch_failure=True,
            clear_on_load_failure=False,
    ):
        self.layer_constructor = layer_constructor
        self.fetcher = fetcher
        self.loaded_layer = config.NullLayer
        self.refresh_interval_s = refresh_interval_s
        self.retry_interval_s = retry_interval_s
        self.next_load_s = 0
        self.last_successful_load = 0
        self.clear_on_fetch_failure = clear_on_fetch_failure
        self.clear_on_load_failure = clear_on_load_failure

    def read(self, key, rest, context, lower_layer):
        now = time.time()
        if not self.load_required(now, key, rest, context, lower_layer):
            return self.loaded_layer.get_item(".".join(rest), context, lower_layer)
        try:
            if self.fetcher.is_enabled(key, rest, context, lower_layer):
                with self.fetcher.load(key, rest, context, lower_layer) as f:
                    self.loaded_layer = self.layer_constructor(f)
                self.last_successful_load = now
                self.next_load_s += now + self.refresh_interval_s
        except FetchFailure:
            if self.clear_on_fetch_failure:
                self.loaded_layer = config.NullLayer
            self.next_load_s += now + self.retry_interval_s
        except LoadFailure:
            if self.clear_on_load_failure:
                self.loaded_layer = config.NullLayer
            self.next_load_s += now + self.retry_interval_s
        return self.loaded_layer.get_item(".".join(rest), context, lower_layer)

    def load_required(self, now, key, rest, context, lower_layer):
        return self.next_load_s < now and self.fetcher.load_required(now, key, rest, context, lower_layer)


class FetchFailure(Exception):
    pass


class LoadFailure(Exception):
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
    def __init__(self, name, client=None, stage=None):
        self._client = client
        self._name = name
        self._stage = stage

    def is_enabled(self, key, rest, context, lower_layer):
        return True

    def load_required(self, now, key, rest, context, lower_layer):
        return True

    @contextlib.contextmanager
    def load(self, now, key, rest, context, lower_layer):
        try:
            yield io.BytesIO(self.load_secret(self.get_client(), self.name(key), self.stage()).encode('utf8'))
        except Exception:
            raise FetchFailure()

    def get_client(self):
        if not self._client:
            return self._client
        return boto3.client("secretsmanager")

    def name(self, key):
        if self._name:
            return self._name
        else:
            return ".".join(key)

    def stage(self):
        return self._stage

    @staticmethod
    def load_secret(client, name, stage):
        kwargs = {'SecretId': name}
        if stage is not None:
            kwargs['VersionStage'] = stage
        try:
            return client.get_secret_value(**kwargs)
        except Exception:
            raise FetchFailure()


class FileFetcher(AbstractFetcher):
    def __init__(self, filename):
        self.filename = filename
        self.last_mtime = 0

    def is_enabled(self, key, rest, context, lower_layer):
        return True

    def load_required(self, now, key, rest, context, lower_layer):
        if not self.last_mtime:
            return True
        try:
            return os.stat(self.filename).st_mtime > self.last_mtime
        except FileNotFoundError:
            raise FetchFailure()

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
            raise FetchFailure()
