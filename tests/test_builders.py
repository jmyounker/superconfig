import datetime

import boto3
import freezegun
import moto
import pytest

import smarts
import superconfig as sc


@moto.mock_ssm
def test_parameterstore_layer_maps_key_as_expected():
    ps = boto3.client("ssm")
    ps.put_parameter(
        Name="/base/a/b",
        Type="String",
        Value="foo",
    )
    c = sc.config_stack(sc.aws_parameter_store_layer("/base"))
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
    c = sc.config_stack(
        sc.aws_parameter_store_layer(
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
    c = sc.config_stack(
        sc.aws_parameter_store_layer(
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
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value()}),
        sc.ObjLayer({"a": {"b": "1"}}),
    )
    assert c["a.b"] == "1"


def test_value_pulls_from_all_the_way_below():
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value()}),
        sc.ObjLayer({}),
        sc.ObjLayer({"a": {"b": "1"}}),
    )
    assert c["a.b"] == "1"


def test_performs_transform():
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(transform=int)}),
        sc.ObjLayer({"a": {"b": "1"}}),
    )
    assert c["a.b"] == 1


def test_with_single_envar_pulls_from_envar(monkeypatch):
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(envar="FOO")}),
        sc.ObjLayer({"a": {"b": "1"}}),

    )
    monkeypatch.setenv("FOO", "2")
    assert c["a.b"] == "2"


def test_with_single_envar_pulls_from_below_if_envar_missing(monkeypatch):
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(envar="FOO")}),
        sc.ObjLayer({"a": {"b": "1"}}),

    )
    monkeypatch.delenv("FOO", raising=False)
    assert c["a.b"] == "1"

def test_with_multi_envars_finds_first_one(monkeypatch):
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(envars=["FOO", "BAR"])}),
        sc.ObjLayer({"a": {"b": "1"}}),

    )
    monkeypatch.setenv("FOO", "2")
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == "2"


def test_with_multi_envars_moves_to_second_if_first_missing(monkeypatch):
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(envars=["FOO", "BAR"])}),
        sc.ObjLayer({"a": {"b": "1"}}),

    )
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == "3"


def test_with_envar_and_envars_foo_stacks_first(monkeypatch):
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(envar="FOO", envars=["BAR"])}),
        sc.ObjLayer({"a": {"b": "1"}}),
    )
    monkeypatch.setenv("FOO", "2")
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == "2"


def test_with_envar_and_envars_list_stacks_afterwards(monkeypatch):
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(envar="FOO", envars=["BAR"])}),
        sc.ObjLayer({"a": {"b": "1"}}),
    )
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == "3"


def test_transform_affects_envars(monkeypatch):
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(envar="FOO", envars=["BAR"], transform=int)}),
        sc.ObjLayer({"a": {"b": "1"}}),
    )
    monkeypatch.setenv("FOO", "2")
    monkeypatch.setenv("BAR", "3")
    assert c["a.b"] == 2


def test_missing_value_raises_key_error_with_transform():
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(transform=int)}),
    )
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_missing_value_raises_key_error_without_transform_too():
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value()}),
    )
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_with_default():
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(default="1")}),
    )
    assert c["a.b"] == "1"


def test_default_passes_through_transform():
    c = sc.config_stack(
        sc.SmartLayer({"a.b": sc.value(default="1", transform=int)}),
    )
    assert c["a.b"] == 1
