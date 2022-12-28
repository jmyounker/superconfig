import base64

import boto3
import moto
import pytest

from superconfig import aws
from superconfig import builders
from superconfig import config
from superconfig import converters
from superconfig import loaders
from superconfig import gtrs
from superconfig import statics
from superconfig import let


@moto.mock_secretsmanager
def test_secmgr_load_single_value_string():
    sm = boto3.client("secretsmanager")
    sm.create_secret(
        Name='a.b',
        SecretString='foo',
    )
    c = config.layered_config(
            config.Context(),
            [
                gtrs.GetterLayer(
                    {
                        "a.b": loaders.AutoRefreshGetter(
                            layer_constructor=lambda f: config.ConstantLayer(
                                converters.string_from_bytes(f, encoding='utf8')),
                            fetcher=aws.SecretsManagerFetcher(),
                        )
                    }
                ),
            ]
        )
    assert c["a.b"] == "foo"


@moto.mock_secretsmanager
def test_secmgr_load_single_value_binary():
    sm = boto3.client("secretsmanager")
    sm.create_secret(
        Name='a.b',
        SecretBinary='foo'.encode('utf8'),
    )
    c = config.layered_config(
        config.Context(),
        [
            gtrs.GetterLayer(
                {
                    "a.b": loaders.AutoRefreshGetter(
                        layer_constructor=lambda f: config.ConstantLayer(f),
                        fetcher=aws.SecretsManagerFetcher(),
                    )
                }
            ),
        ]
    )
    assert c["a.b"] == "foo".encode('utf8')


@moto.mock_secretsmanager
def test_secmgr_load_single_value_binary_base64_encoded():
    sm = boto3.client("secretsmanager")

    sm.create_secret(
        Name='a.b',
        SecretBinary=base64.b64encode(b'foo'),
    )
    c = config.layered_config(
        config.Context(),
        [
            gtrs.GetterLayer(
                {
                    "a.b": loaders.AutoRefreshGetter(
                        layer_constructor=lambda f: config.ConstantLayer(f),
                        fetcher=aws.SecretsManagerFetcher(
                            binary_decoder=lambda x: converters.bytes_from_base64(converters.string_from_bytes(x)),
                        ),

                    )
                }
            ),
        ]
    )
    assert c["a.b"] == "foo".encode('utf8')


@moto.mock_secretsmanager
def test_secmgr_load_from_static_name():
    sm = boto3.client("secretsmanager")
    sm.create_secret(
        Name='c.d',
        SecretString='foo',
    )
    c = config.layered_config(
        config.Context(),
        [
            gtrs.GetterLayer(
                {
                    "a.b": loaders.AutoRefreshGetter(
                        layer_constructor=lambda f: config.ConstantLayer(
                            converters.string_from_bytes(f)),
                        fetcher=aws.SecretsManagerFetcher(
                            name=let.compile("c.d")
                        ),
                    )
                }
            ),
        ]
    )
    assert c["a.b"] == "foo"


@moto.mock_secretsmanager
def test_secmgr_load_from_name_template():
    sm = boto3.client("secretsmanager")
    sm.create_secret(
        Name='c-prod',
        SecretString='foo',
    )
    c = config.layered_config(
        config.Context(),
        [
            gtrs.GetterLayer(
                {
                    "a.b": loaders.AutoRefreshGetter(
                        layer_constructor=lambda f: config.ConstantLayer(
                            converters.string_from_bytes(f)),
                        fetcher=aws.SecretsManagerFetcher(
                            name=let.compile("c-{env}")
                        ),
                    )
                }
            ),
            gtrs.GetterLayer({
                "env": gtrs.Constant("prod"),
            }),
        ]
    )
    assert c["a.b"] == "foo"


@moto.mock_secretsmanager
def test_secmgr_load_from_name_template_fails():
    sm = boto3.client("secretsmanager")
    sm.create_secret(
        Name='c-you-wont-find-this',
        SecretString='foo',
    )
    c = config.layered_config(
        config.Context(),
        [
            gtrs.GetterLayer(
                {
                    "a.b": loaders.AutoRefreshGetter(
                        layer_constructor=lambda f: config.ConstantLayer(
                            converters.string_from_bytes(f)),
                        fetcher=aws.SecretsManagerFetcher(
                            name="c-{env}"
                        ),
                    )
                }
            ),
            gtrs.GetterLayer({
                "env": gtrs.Constant("prod"),
            }),
        ]
    )
    with pytest.raises(KeyError):
        _ = c["a.b"]


@moto.mock_ssm
def test_parameterstore_implicit_tree_root():
    ps = boto3.client("ssm")
    ps.put_parameter(
        Name="/a/b",
        Type="String",
        Value="foo",
    )
    c = config.Config(config.Context(), gtrs.GetterLayer({"a": builders.aws_parameter_store_getter()}))
    assert c["a.b"] == "foo"


@moto.mock_ssm
def test_parameterstore_explicit_tree_root():
    ps = boto3.client("ssm")
    ps.put_parameter(
        Name="/c/b",
        Type="String",
        Value="foo",
    )
    c = config.Config(config.Context(), gtrs.GetterLayer({"a": builders.aws_parameter_store_getter("/c")}))
    assert c["a.b"] == "foo"


@moto.mock_ssm
def test_parameter_store_value_handling():
    ps = boto3.client("ssm")
    ps.put_parameter(
        Name='/a/b/c',
        Type='String',
        Value='1',
    )
    ps.put_parameter(
        Name='/a/b/c/d',
        Type='StringList',
        Value='2a,2b',
    )
    ps.put_parameter(
        Name='/a/b/c/e',
        Type='SecureString',
        Value=base64.b64encode(b'3').decode('utf8'),
    )
    c = config.Config(config.Context(), gtrs.GetterLayer({
        "a": builders.aws_parameter_store_getter(
            "/a",
            binary_decoder=converters.bytes_from_base64)}))
    assert c["a.b.c"] == "1"
    assert c["a.b.c.d"] == ["2a", "2b"]
    # There are significant differences between what moto returns and what real AWS, so
    # this is as good as I can get for the moment.
    assert c["a.b.c.e"] == b"3"


@moto.mock_ssm
def test_parameterstore_path_expansion():
    ps = boto3.client("ssm")
    ps.put_parameter(
        Name="/a/stage/root/c",
        Type="String",
        Value="foo",
    )
    c = config.layered_config(
        config.Context(),
        [
            gtrs.GetterLayer({"a": builders.aws_parameter_store_getter("/a/{env}/root")}),
            statics.ObjLayer({"env": "stage"}),
        ]
    )
    assert c["a.c"] == "foo"
