import base64

import boto3
import moto
import pytest

import aws
import converters
import superconfig as sc
import vars


@moto.mock_secretsmanager
def test_secmgr_load_single_value_string():
    sm = boto3.client("secretsmanager")
    sm.create_secret(
        Name='a.b',
        SecretString='foo',
    )
    c = sc.layered_config(
            sc.Context(),
            [
                sc.SmartLayer(
                    {
                        "a.b": sc.AutoRefreshGetter(
                            layer_constructor=lambda f: sc.ConstantLayer(
                                sc.string_from_bytes(f, encoding='utf8')),
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
    c = sc.layered_config(
        sc.Context(),
        [
            sc.SmartLayer(
                {
                    "a.b": sc.AutoRefreshGetter(
                        layer_constructor=lambda f: sc.ConstantLayer(f),
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
    c = sc.layered_config(
        sc.Context(),
        [
            sc.SmartLayer(
                {
                    "a.b": sc.AutoRefreshGetter(
                        layer_constructor=lambda f: sc.ConstantLayer(f),
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
    c = sc.layered_config(
        sc.Context(),
        [
            sc.SmartLayer(
                {
                    "a.b": sc.AutoRefreshGetter(
                        layer_constructor=lambda f: sc.ConstantLayer(
                            sc.string_from_bytes(f)),
                        fetcher=aws.SecretsManagerFetcher(
                            name=vars.compile("c.d")
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
    c = sc.layered_config(
        sc.Context(),
        [
            sc.SmartLayer(
                {
                    "a.b": sc.AutoRefreshGetter(
                        layer_constructor=lambda f: sc.ConstantLayer(
                            sc.string_from_bytes(f)),
                        fetcher=aws.SecretsManagerFetcher(
                            name=vars.compile("c-{env}")
                        ),
                    )
                }
            ),
            sc.SmartLayer({
                "env": sc.Constant("prod"),
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
    c = sc.layered_config(
        sc.Context(),
        [
            sc.SmartLayer(
                {
                    "a.b": sc.AutoRefreshGetter(
                        layer_constructor=lambda f: sc.ConstantLayer(
                            sc.string_from_bytes(f)),
                        fetcher=aws.SecretsManagerFetcher(
                            name="c-{env}"
                        ),
                    )
                }
            ),
            sc.SmartLayer({
                "env": sc.Constant("prod"),
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
    c = sc.Config(sc.Context(), sc.SmartLayer({"a": sc.aws_parameter_store_getter()}))
    assert c["a.b"] == "foo"


@moto.mock_ssm
def test_parameterstore_explicit_tree_root():
    ps = boto3.client("ssm")
    ps.put_parameter(
        Name="/c/b",
        Type="String",
        Value="foo",
    )
    c = sc.Config(sc.Context(), sc.SmartLayer({"a": sc.aws_parameter_store_getter("/c")}))
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
    c = sc.Config(sc.Context(), sc.SmartLayer({
        "a": sc.aws_parameter_store_getter(
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
    c = sc.layered_config(
        sc.Context(),
        [
            sc.SmartLayer({"a": sc.aws_parameter_store_getter("/a/{env}/root")}),
            sc.ObjLayer({"env": "stage"}),
        ]
    )
    assert c["a.c"] == "foo"
