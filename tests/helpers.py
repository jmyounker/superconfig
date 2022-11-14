import pytest


def is_expected_getitem(config, key, res):
    if res is KeyError:
        with pytest.raises(KeyError):
            _ = config[key]
        return True
    else:
        return config[key] == res
