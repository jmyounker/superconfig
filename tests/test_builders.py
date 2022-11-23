import datetime

import boto3
import freezegun
import moto

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
            refresh_interval_s=refresh_interval_s,
            ttl_s=ttl_s,
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
            refresh_interval_s=refresh_interval_s,
            ttl_s=ttl_s,
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
