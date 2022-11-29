import contextlib
import os
import time
import threading
from typing import Any
from typing import Tuple

import aenum

import config
import exceptions
import helpers
import smarts


class AtomicRef:
    def __init__(self, x):
        self.value = {"": x}

    def get(self):
        return self.value[""]

    def set(self, x):
        self.value[""] = x


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
            refresh_interval_s=smarts.constant(60),
            retry_interval_s=smarts.constant(10),
            clear_on_removal=True,
            clear_on_fetch_failure=False,
            clear_on_load_failure=False,
            is_enabled=None
    ):
        self.load_lock = threading.Lock()
        self.layer_constructor = layer_constructor
        self.fetcher = fetcher
        self.loaded_layer = AtomicRef(config.NullLayer)
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
            return self.loaded_layer.get().get_item(".".join(rest), context, lower_layer)
        if self.load_lock.acquire(blocking=False):
            try:
                if self.is_enabled(key, rest, context, lower_layer):
                    with self.fetcher.load(now, key, rest, context, lower_layer) as f:
                        if f is not None:
                            self.loaded_layer.set(self.layer_constructor(f))
                    self.last_successful_load = now
                    self.next_load_s += now + self.refresh_interval_s(context, lower_layer)
            except exceptions.DataSourceMissing:
                if self.clear_on_removal:
                    self.loaded_layer.set(config.NullLayer)
                self.next_load_s = now + self.retry_interval_s(context, lower_layer)
            except exceptions.FetchFailure:
                if self.clear_on_fetch_failure:
                    self.loaded_layer.set(config.NullLayer)
                self.next_load_s += now + self.retry_interval_s(context, lower_layer)
            except exceptions.LoadFailure:
                if self.clear_on_load_failure:
                    self.loaded_layer.set(config.NullLayer)
                self.next_load_s += now + self.retry_interval_s(context, lower_layer)
            except Exception:
                if self.clear_on_fetch_failure:
                    self.loaded_layer.set(config.NullLayer)
                self.next_load_s += now + self.retry_interval_s(context, lower_layer)
            finally:
                self.load_lock.release()
        return self.loaded_layer.get().get_item(".".join(rest), context, lower_layer)

    @staticmethod
    def always_enabled(key, rest, context, lower_layer):
        return True


class AbstractFetcher:
    """Fetchers obtain read-only binary file objects from external sources."""
    @contextlib.contextmanager
    def load(self, now, key, rest, context, lower_layer):
        raise NotImplementedError


class FileFetcher(AbstractFetcher):
    def __init__(self, filename_tmpl):
        self.name = helpers.ExpandableString(filename_tmpl)
        self.last_mtime = 0

    def load_required(self, filename):
        # The expansion works because there is an implicit sequencing between
        # these two calls.
        if not self.last_mtime:
            return True
        try:
            return os.stat(filename).st_mtime > self.last_mtime
        except FileNotFoundError:
            raise exceptions.DataSourceMissing()

    @contextlib.contextmanager
    def load(self, now, key, rest, context, lower_layer):
        filename = self.name.expand(context, lower_layer)
        if filename is None:
            raise exceptions.FetchFailure()

        if not self.load_required(filename):
            yield None
            return

        try:
            # Get stat before, so if the file is updated after the stat, then it will
            # be found as out-of-date on the next load.
            s = os.stat(filename)
            with open(filename, 'rb') as f:
                yield f.read()
            self.last_mtime = s.st_mtime
        except FileNotFoundError:
            raise exceptions.DataSourceMissing()
        except IOError:
            raise exceptions.FetchFailure()


class FileLayerLoader:
    def __init__(
            self,
            layer_constructor,
            filename,
            refresh_interval_s=smarts.constant(10),
            retry_interval_s=smarts.constant(5),
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


@aenum.unique
class Format(aenum.Enum):
    pass


def register_format(x):
    aenum.extend_enum(Format, x, x.lower())


register_format("Ini")
register_format("Json")
register_format("Properties")
register_format("Toml")
register_format("Yaml")

