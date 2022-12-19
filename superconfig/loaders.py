import contextlib
import os
import time
import threading

import config
import exceptions
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
        self.is_enabled = is_enabled or smarts.constant(True)

    def read(self, key, rest, context, lower_layer):
        now = time.time()
        if self.next_load_s >= now:
            return self.loaded_layer.get().get_item(".".join(rest), context, lower_layer)
        if self.load_lock.acquire(blocking=False):
            try:
                if self.is_enabled(context, lower_layer):
                    with self.fetcher.load(now, key, rest, context, lower_layer) as bin_data:
                        if bin_data is not None:
                            self.loaded_layer.set(self.layer_constructor(bin_data))
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
            except Exception as e:
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


def simple_reader(filename):
    with open(filename, 'rb') as f:
        return f.read()


class FileFetcher(AbstractFetcher):
    def __init__(self, filename_value, reader=simple_reader):
        self.name = filename_value
        self.filename = None
        self.last_mtime = 0
        if reader is None:
            self.reader = simple_reader
        else:
            self.reader = reader

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
        filename = self.name(context, lower_layer)
        if filename is None:
            raise exceptions.FetchFailure()

        # Not sure if this belongs here or after load_required() call.
        self.filename = filename

        if not self.load_required(filename):
            yield None
            return

        try:
            # Get stat before, so if the file is updated after the stat, then it will
            # be found as out-of-date on the next load.
            s = os.stat(filename)
            yield self.reader(filename)
            self.last_mtime = s.st_mtime
        except FileNotFoundError:
            raise exceptions.DataSourceMissing()
        except IOError:
            raise exceptions.FetchFailure()
        except Exception:
            raise

