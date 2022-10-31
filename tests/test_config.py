import pytest

from superconfig import Config
from superconfig import DictLayer
from superconfig import Context


def test_getitem():
    test_cases = [
        ({"a":1, "b": 2}, "a", 1),
        ({"a":1, "b": 2}, "b", 2),
        ({"a":1, "b": 2}, "c", KeyError),
        ({"a": {"b": 1}}, "a", KeyError),
        ({"a": {"b": 1}}, "a.b", 1),
        ({"a": {"b": 1}}, "a.c", KeyError),
        ({"a": {"b": 1}}, "b", KeyError),
        ({"a": {"b": 1}}, "c", KeyError),
    ]
    for (d, k, res) in test_cases:
        config = Config(Context(), DictLayer(d))
        if res is KeyError:
            with pytest.raises(KeyError):
                _ = config[k]
        else:
            assert config[k] == res


def test_get():
    test_cases = [
        ({"a":1, "b": 2}, "a", None, 1),
        ({"a":1, "b": 2}, "b", None, 2),
        ({"a":1, "b": 2}, "c", None, None),
        ({"a":1, "b": 2}, "c", 3, 3),
        ({"a": {"b": 1}}, "a", None, None),
        ({"a": {"b": 1}}, "a", 3, 3),
        ({"a": {"b": 1}}, "a.b", None, 1),
        ({"a": {"b": 1}}, "a.c", None, None),
        ({"a": {"b": 1}}, "a.c", 3, 3),
        ({"a": {"b": 1}}, "b", None, None),
        ({"a": {"b": 1}}, "b", 3, 3),
        ({"a": {"b": 1}}, "c", None, None),
        ({"a": {"b": 1}}, "c", 3, 3),
    ]
    for (d, k, default, res) in test_cases:
        config = Config(Context(), DictLayer(d))
        assert config.get(k, default) == res

