import pytest

import superconfig as sc
from tests.helpers import is_expected_getitem


def test_load_config_from_json_string():
    config = """{"a":{"b": 1}}"""
    c = sc.Config(sc.Context(), sc.ObjLayer(sc.obj_from_json(config)))
    assert is_expected_getitem(c, "a.b", 1)


def test_load_obj_from_json_string_with_error():
    config = ":-b\nc:\n"
    with pytest.raises(sc.LoadFailure):
        sc.obj_from_json(config)


def test_load_config_from_yaml_string():
    config = """# A YAML test file
a:
  b: 1

"""
    c = sc.Config(sc.Context(), sc.ObjLayer(sc.obj_from_yaml(config)))
    assert is_expected_getitem(c, "a.b", 1)


def test_load_obj_from_yaml_string():
    config = """# A YAML test file
a:
  b: 1

"""
    assert sc.obj_from_yaml(config) == {"a": {"b": 1}}


def test_load_obj_from_yaml_string_with_error():
    config = ":-b\nc:\n"
    with pytest.raises(sc.LoadFailure):
        sc.obj_from_yaml(config)
