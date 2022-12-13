import base64
import datetime
import json

import boto3
import freezegun
import moto
import pytest

from superconfig import builders
from superconfig import formats
from superconfig import smarts
from superconfig import statics


@moto.mock_ssm
def test_parameterstore_layer_maps_key_as_expected():
    ps = boto3.client("ssm")
    ps.put_parameter(
        Name="/base/a/b",
        Type="String",
        Value="foo",
    )
    c = builders.config_stack(builders.aws_parameter_store_layer("/base"))
    assert c["a.b"] == "foo"


@moto.mock_ssm
def test_parameterstore_layer_get_caches_before_ttl():
    create_record_at_s = 0
    initial_read_at_s = 5
    update_paramstore_at_s = 10
    post_update_read_at_s = 15
    ttl_s=30
    refresh_interval_s = 60

    ps = boto3.client("ssm")
    c = builders.config_stack(
        builders.aws_parameter_store_layer(
            parameter_store_base_path="/base",
            refresh_interval_s=smarts.constant(refresh_interval_s),
            ttl_s=smarts.constant(ttl_s),
        ),
    )
    now = datetime.datetime.utcnow()
    with freezegun.freeze_time(now + datetime.timedelta(seconds=create_record_at_s)):
        ps.put_parameter(
            Name="/base/a/b",
            Type="String",
            Value="foo",
        )
    with freezegun.freeze_time(now + datetime.timedelta(seconds=initial_read_at_s)):
        assert c["a.b"] == "foo"
    with freezegun.freeze_time(now + datetime.timedelta(seconds=update_paramstore_at_s)):
        ps.put_parameter(
            Name="/base/a/b",
            Type="String",
            Value="bar",
            Overwrite=True,
        )
    with freezegun.freeze_time(now + datetime.timedelta(seconds=post_update_read_at_s)):
        assert c["a.b"] == "foo"


@moto.mock_ssm
def test_parameterstore_layer_refreshes_after_ttl():
    create_record_at_s = 0
    initial_read_at_s = 5
    update_paramstore_at_s = 10
    ttl_s=30
    post_update_read_at_s = 35
    refresh_interval_s = 60

    ps = boto3.client("ssm")
    c = builders.config_stack(
        builders.aws_parameter_store_layer(
            parameter_store_base_path="/base",
            refresh_interval_s=smarts.constant(refresh_interval_s),
            ttl_s=smarts.constant(ttl_s),
        ),
    )
    now = datetime.datetime.utcnow()
    with freezegun.freeze_time(now + datetime.timedelta(seconds=create_record_at_s)):
        ps.put_parameter(
            Name="/base/a/b",
            Type="String",
            Value="foo",
        )
    with freezegun.freeze_time(now + datetime.timedelta(seconds=initial_read_at_s)):
        assert c["a.b"] == "foo"
    with freezegun.freeze_time(now + datetime.timedelta(seconds=update_paramstore_at_s)):
        ps.put_parameter(
            Name="/base/a/b",
            Type="String",
            Value="bar",
            Overwrite=True,
        )
    with freezegun.freeze_time(now + datetime.timedelta(seconds=post_update_read_at_s)):
        assert c["a.b"] == "bar"


def test_value_pulls_from_below():
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value()}),
        statics.ObjLayer({"a": {"b": "1"}}),
    )
    assert c["a.b"] == "1"


def test_value_pulls_from_all_the_way_below():
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value()}),
        statics.ObjLayer({}),
        statics.ObjLayer({"a": {"b": "1"}}),
    )
    assert c["a.b"] == "1"


def test_performs_transform():
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(transform=int)}),
        statics.ObjLayer({"a": {"b": "1"}}),
    )
    assert c["a.b"] == 1


def test_with_single_envar_pulls_from_envar(monkeypatch):
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(envar="FOO")}),
        statics.ObjLayer({"a": {"b": "1"}}),

    )
    monkeypatch.setenv("FOO", "2")
    assert c["a.b"] == "2"


def test_with_single_envar_pulls_from_below_if_envar_missing(monkeypatch):
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(envar="FOO")}),
        statics.ObjLayer({"a": {"b": "1"}}),

    )
    monkeypatch.delenv("FOO", raising=False)
    assert c["a.b"] == "1"

def test_with_multi_envars_finds_first_one(monkeypatch):
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(envars=["FOO", "BAR"])}),
        statics.ObjLayer({"a": {"b": "1"}}),

    )
    monkeypatch.setenv("FOO", "2")
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == "2"


def test_with_multi_envars_moves_to_second_if_first_missing(monkeypatch):
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(envars=["FOO", "BAR"])}),
        statics.ObjLayer({"a": {"b": "1"}}),

    )
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == "3"


def test_with_envar_and_envars_foo_stacks_first(monkeypatch):
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(envar="FOO", envars=["BAR"])}),
        statics.ObjLayer({"a": {"b": "1"}}),
    )
    monkeypatch.setenv("FOO", "2")
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == "2"


def test_with_envar_and_envars_list_stacks_afterwards(monkeypatch):
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(envar="FOO", envars=["BAR"])}),
        statics.ObjLayer({"a": {"b": "1"}}),
    )
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == "3"


def test_transform_affects_envars(monkeypatch):
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(envar="FOO", envars=["BAR"], transform=int)}),
        statics.ObjLayer({"a": {"b": "1"}}),
    )
    monkeypatch.setenv("FOO", "2")
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == 2


def test_missing_value_raises_key_error_with_transform():
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(transform=int)}),
    )
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_values_chain_across_layers():
    c = builders.config_stack(
        {"a.b": builders.value()},
        {"a.b": builders.value(default=2)},
        {"a.b": builders.value()},
    )
    assert c["a.b"] == 2


def test_stop_overrides_further_defaults():
    c = builders.config_stack(
        {"a.b": builders.value(default=2)},
        {"a.b": builders.value(stop=True)},
    )
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_default_and_stop_are_incompatible():
    with pytest.raises(ValueError):
        builders.value(default=2, stop=True)


def test_missing_value_raises_key_error_without_transform_too():
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value()}),
    )
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_with_default():
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(default="1")}),
    )
    assert c["a.b"] == "1"


def test_default_passes_through_transform():
    c = builders.config_stack(
        smarts.SmartLayer({"a.b": builders.value(default="1", transform=int)}),
    )
    assert c["a.b"] == 1


def test_autoload_format_by_extension(tmp_path):
    test_cases = [
        ('{"a": {"b": 1}}\n', "foo.json", "a.b", 1),
        ('a:\n  b: 1\n', "foo.yaml", "a.b", 1),
        ('a:\n  b: 1\n', "foo.yml", "a.b", 1),
        ('[a]\nb = 1\n', "foo.ini", "a.b", "1"),
        ('[a]\nb = 1\n', "foo.toml", "a.b", 1),
        ('a.b = 1\n', "foo.prop", "a.b", "1"),
        ('a.b = 1\n', "foo.props", "a.b", "1"),
        ('a.b = 1\n', "foo.properties", "a.b", "1"),
    ]
    for contents, filename, key, expected_value in test_cases:
        f = tmp_path / filename
        f.write_text(contents)
        c = builders.config_stack(
            builders.file_layer(filename=f)
        )
        assert c[key] == expected_value


@moto.mock_secretsmanager
def test_aws_secretsmanager_getter():
    sm = boto3.client("secretsmanager")
    x = {
        "c": {
            "d": 1,
        }
    }
    sm.create_secret(
        Name='a.b',
        SecretBinary=base64.b64encode(json.dumps(x).encode('utf8')),
    )
    c = builders.config_stack(
        {"a.b": builders.aws_secretsmanager_getter(
            format=formats.Format.Json,
            binary_decoder=builders.Decoders.base64
        )},
    )
    assert c["a.b.c.d"] == 1
