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


class FetchFailure(Exception):
    pass


class DataSourceMissing(Exception):
    pass


class LoadFailure(Exception):
    pass
