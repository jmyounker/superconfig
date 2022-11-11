import datetime
import json

import boto3
import freezegun
import moto
import pytest

import superconfig as sc


def test_file_layer_loader_file_missing(tmp_path):
    c = sc.layered_config([sc.FileLayerLoader(sc.JsonLayer.from_file, str(tmp_path / "foo.json"))])
    with pytest.raises(KeyError):
        _ = c["a"]


def test_file_layer_loader_loads_files(tmp_path):
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [sc.FileLayerLoader(sc.JsonLayer.from_file, str(f))])
    assert c["a"] == 1


def test_file_layer_loader_does_not_reload_during_cache_period(tmp_path):
    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            refresh_interval_s=check_period_s,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        f.write_text(json.dumps({"a": 2}))
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s-1)):
        assert c["a"] == 1


def test_file_layer_loader_does_not_load_unchanged_files(tmp_path):
    loaded = [False]

    def load_checking_loader(f):
        loaded[0] = True
        return sc.JsonLayer.from_file(f)

    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            load_checking_loader,
            str(f),
            refresh_interval_s=check_period_s,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        assert loaded[0]
        loaded[0] = False
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s+1)):
        assert c["a"] == 1
        assert not loaded[0]


def test_file_layer_loader_loads_changed_files_after_cache_period(tmp_path):
    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            refresh_interval_s=check_period_s,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        f.write_text(json.dumps({"a": 2}))
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s+1)):
        assert c["a"] == 2


def test_file_layer_loader_w_clear_clears_config_after_file_removed(tmp_path):
    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            refresh_interval_s=check_period_s,
            clear_on_removal=True,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        f.unlink()
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s+1)):
        with pytest.raises(KeyError):
            _ = c["a"]


def test_file_layer_loader_wo_clear_keeps_config_after_file_removal(tmp_path):
    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            refresh_interval_s=check_period_s,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        f.unlink()
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s+1)):
        assert c["a"] == 1


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
                                sc.string_from_bytes(sc.bytes_from_file(f), encoding='utf8')),
                            fetcher=sc.SecretsManagerFetcher(),
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
                        layer_constructor=lambda f: sc.ConstantLayer(sc.bytes_from_file(f)),
                        fetcher=sc.SecretsManagerFetcher(),
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
                            sc.string_from_bytes(sc.bytes_from_file(f))),
                        fetcher=sc.SecretsManagerFetcher(
                            name="c.d"
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
                            sc.string_from_bytes(sc.bytes_from_file(f))),
                        fetcher=sc.SecretsManagerFetcher(
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
                            sc.string_from_bytes(sc.bytes_from_file(f))),
                        fetcher=sc.SecretsManagerFetcher(
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


def test_autoload_enabled_when_true(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            refresh_interval_s=check_period_s,
            is_enabled=sc.config_switch("sc.file_layer.is_enabled"),
        ),
        sc.SmartLayer({
            "sc.file_layer.is_enabled": sc.Constant(True),
        }),
    ])
    assert c["a"] == 1


def test_autoload_disabled_when_false(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            refresh_interval_s=check_period_s,
            is_enabled=sc.config_switch("sc.file_layer.is_enabled"),
        ),
        sc.SmartLayer({
            "sc.file_layer.is_enabled": sc.Constant(False),
        }),
    ])
    with pytest.raises(KeyError):
        _ = c["a"]


def test_autoload_disabled_when_missing(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            refresh_interval_s=check_period_s,
            is_enabled=sc.config_switch("sc.file_layer.is_enabled"),
        ),
    ])
    with pytest.raises(KeyError):
        _ = c["a"]


def test_autoload_filename_expansion_works(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo-prod.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            sc.JsonLayer.from_file,
            str(tmp_path / "foo-{env}.json"),
            refresh_interval_s=check_period_s,
        ),
        sc.SmartLayer({
            "env": sc.Constant("prod"),
        }),
    ])
    assert c["a"] == 1


def test_autoload_filename_expansion_fails(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo-prod.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.FileLayerLoader(
            sc.JsonLayer.from_file,
            str(tmp_path / "foo-{env}.json"),
            refresh_interval_s=check_period_s,
        ),
    ])
    with pytest.raises(KeyError):
        _ = c["a"]

