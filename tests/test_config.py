import pytest

from .helpers import is_expected_getitem
from config import LayerCake
from config import layered_config
from superconfig import Config, LoadFailure
from superconfig import ObjLayer
from superconfig import InnerObjLayer
from superconfig import IniLayer
from superconfig import Context
from superconfig import ConstantLayer


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
        config = Config(Context(), ObjLayer(d))
        assert is_expected_getitem(config, k, res)


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
        config = Config(Context(), ObjLayer(d))
        assert config.get(k, default) == res


def test_layering_getitem():
    test_cases = [
        ([], "a", KeyError),
        ([{"a":1}], "a", 1),
        ([{"a":1}], "b", KeyError),
        ([{"a":1}, {"b": 2}], "a", 1),
        ([{"a":1}, {"b": 2}], "b", 2),
        ([{"a":1}, {"a": 3, "b": 2}], "a", 3),
        ([{"a":1}, {"a": 3, "b": 2}], "b", 2),
        ([{"a":1}, {"a": 3, "b": 2}], "c", KeyError),
        ([{"a": {"b": 1}}, {"a": 2}], "a", 2),
        ([{"a": {"b": 1}}, {"a": 2}], "a.b", 1),
        ([{"a": 1}, {"a": 2}], "a", 2),
    ]
    for (layers, k, res) in test_cases:
        layer_cake = LayerCake()
        for layer in layers:
            layer_cake.push(ObjLayer(layer))
        config = Config(Context(), layer_cake)
        assert is_expected_getitem(config, k, res)


def test_layered_config():
    test_cases = [
        ([], "a", KeyError),
        ([{"a": 1}], "a", 1),
        ([{"a": 1}, {"a": 2}], "a", 1),
        ([{"a": 1}, {"a": 2, "b": 3}], "b", 3),
        ([{"a": 1}, {"a": 2, "b": 3}], "c", KeyError),
    ]
    for (layers, k, res) in test_cases:
        config = layered_config(Context(), [ObjLayer(x) for x in layers])
        assert is_expected_getitem(config, k, res)


def test_inner_obj_layer():
    test_cases = [
        ({}, "a", KeyError),
        ({"a":1}, "a", 1),
        ({"a":1, "b": 2}, "a", 1),
        ({"a":1, "b": 2}, "b", 2),
        ({"a":1, "b": 2}, "c", KeyError),
        ({"a": {"b": 2}}, "a", {"b": 2}),
        ({"a": {"b": 2}}, "a.b", 2),
        ({"a": {"b": [1, 2]}}, "a.b", [1, 2]),
    ]
    for (d, k, res) in test_cases:
        config = Config(Context(), InnerObjLayer(d))
        assert is_expected_getitem(config, k, res)


def test_constant_layer():
    config = Config(Context(), ConstantLayer(1))
    assert is_expected_getitem(config, "", 1)
    assert is_expected_getitem(config, "a", 1)
    assert is_expected_getitem(config, "a.b", 1)


def test_ini_layer():
    test_cases = [
        ("""# An INI file
[a]
  b: 1
    
    """, [("a", KeyError), ("a.b", "1")],
         ),
    ]
    for ini, cases in test_cases:
        c = Config(Context(), IniLayer.from_string(ini))
        for k, expected_v in cases:
            assert is_expected_getitem(c, k, expected_v)


def test_ini_load_failure():
    with pytest.raises(LoadFailure):
        _ = Config(Context(), IniLayer.from_string("""[foo"""))
