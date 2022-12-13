import pytest

from superconfig import config
from superconfig import exceptions
from superconfig import statics
from superconfig import converters

from tests.helpers import is_expected_getitem


def test_load_config_from_json_string():
    cfg = """{"a":{"b": 1}}"""
    c = config.Config(config.Context(), statics.ObjLayer(converters.obj_from_json(cfg)))
    assert is_expected_getitem(c, "a.b", 1)


def test_load_obj_from_json_string_with_error():
    cfg = ":-b\nc:\n"
    with pytest.raises(exceptions.LoadFailure):
        converters.obj_from_json(cfg)
        assert False

def test_load_config_from_yaml_string():
    cfg = """# A YAML test file
a:
  b: 1

"""
    c = config.Config(config.Context(), statics.ObjLayer(converters.obj_from_yaml(cfg)))
    assert is_expected_getitem(c, "a.b", 1)


def test_load_obj_from_yaml_string():
    cfg = """# A YAML test file
a:
  b: 1

"""
    assert converters.obj_from_yaml(cfg) == {"a": {"b": 1}}


def test_load_obj_from_yaml_string_with_error():
    cfg = ":-b\nc:\n"
    with pytest.raises(exceptions.LoadFailure):
        try:
            converters.obj_from_yaml(cfg)
            assert False
        except Exception as e:
            raise


def test_load_obj_from_toml_string():
    cfg = """# This is a comment
[a]
b=1

[a.c]
d=2
"""
    assert converters.obj_from_toml(cfg) == {"a": {"b": 1, "c": {"d": 2}}}


def test_load_obj_from_toml_string_with_error():
    cfg = """# This is a comment
[a]
b=1
[a.b]
"""
    with pytest.raises(exceptions.LoadFailure):
        converters.obj_from_toml(cfg)
