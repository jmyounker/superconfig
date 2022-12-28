import datetime
import json

import freezegun
import pytest

from superconfig import aws
from superconfig import builders
from superconfig import config
from superconfig import loaders
from superconfig import smarts
from superconfig import statics
from superconfig import let


def test_file_layer_loader_file_missing(tmp_path):
    c = config.layered_config([builders.FileLayerLoader(statics.ObjLayer.from_bytes, let.compile(str(tmp_path / "foo.json")))])
    with pytest.raises(KeyError):
        _ = c["a"]


def test_file_layer_loader_loads_files(tmp_path):
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = config.layered_config(config.Context(), [builders.FileLayerLoader(
        layer_constructor=statics.ObjLayer.from_bytes, filename=let.compile(str(f)))])
    assert c["a"] == 1


def test_file_layer_loader_does_not_reload_during_cache_period(tmp_path):
    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = config.layered_config(config.Context(), [
        builders.FileLayerLoader(
            layer_constructor=statics.ObjLayer.from_bytes,
            filename=let.compile(str(f)),
            refresh_interval_s=let.compile(check_period_s),
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
        return statics.ObjLayer.from_bytes(f)

    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = config.layered_config(config.Context(), [
        builders.FileLayerLoader(
            layer_constructor=load_checking_loader,
            filename=let.compile(str(f)),
            refresh_interval_s=let.compile(check_period_s),
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
    c = config.layered_config(config.Context(), [
        builders.FileLayerLoader(
            layer_constructor=statics.ObjLayer.from_bytes,
            filename=let.compile(str(f)),
            refresh_interval_s=let.compile(check_period_s),
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
    c = config.layered_config(config.Context(), [
        builders.FileLayerLoader(
            layer_constructor=statics.ObjLayer.from_bytes,
            filename=let.compile(str(f)),
            refresh_interval_s=let.compile(check_period_s),
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
    c = config.layered_config(config.Context(), [
        builders.FileLayerLoader(
            layer_constructor=statics.ObjLayer.from_bytes,
            filename=let.compile(str(f)),
            refresh_interval_s=let.compile(check_period_s),
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        f.unlink()
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s+1)):
        assert c["a"] == 1


def test_autoload_enabled_when_true(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = config.layered_config(config.Context(), [
        builders.FileLayerLoader(
            layer_constructor=statics.ObjLayer.from_bytes,
            filename=let.compile(str(f)),
            refresh_interval_s=let.compile((check_period_s)),
            is_enabled=let.compile(let.Key("builders.file_layer.is_enabled")),
        ),
        smarts.SmartLayer({
            "builders.file_layer.is_enabled": smarts.Constant(True),
        }),
    ])
    assert c["a"] == 1


def test_autoload_disabled_when_false(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = config.layered_config(config.Context(), [
        builders.FileLayerLoader(
            layer_constructor=statics.ObjLayer.from_bytes,
            filename=let.compile(str(f)),
            refresh_interval_s=let.compile(check_period_s),
            is_enabled=let.compile(let.Key("builders.file_layer.is_enabled")),
        ),
        smarts.SmartLayer({
            "builders.file_layer.is_enabled": smarts.Constant(False),
        }),
    ])
    with pytest.raises(KeyError):
        _ = c["a"]


def test_autoload_disabled_when_missing(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = config.layered_config(config.Context(), [
        builders.file_layer(
            layer_constructor=statics.ObjLayer.from_bytes,
            filename=let.compile(str(f)),
            refresh_interval_s=let.compile(check_period_s),
            is_enabled=let.compile(let.Key("builders.file_layer.is_enabled")),
        ),
    ])
    with pytest.raises(KeyError):
        _ = c["a"]


def test_autoload_filename_expansion_works(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo-prod.json"
    f.write_text(json.dumps({"a": 1}))
    c = config.layered_config(config.Context(), [
        builders.FileLayerLoader(
            layer_constructor=statics.ObjLayer.from_bytes,
            filename=let.compile(str(tmp_path / "foo-{env}.json")),
            refresh_interval_s=let.compile(check_period_s),
        ),
        smarts.SmartLayer({
            "env": smarts.Constant("prod"),
        }),
    ])
    assert c["a"] == 1


def test_autoload_filename_expansion_fails(tmp_path):
    check_period_s = 3
    f = tmp_path / "foo-prod.json"
    f.write_text(json.dumps({"a": 1}))
    c = config.layered_config(config.Context(), [
        builders.FileLayerLoader(
            layer_constructor=statics.ObjLayer.from_bytes,
            filename=let.compile(str(tmp_path / "foo-{env}.json")),
            refresh_interval_s=let.compile(check_period_s),
        ),
    ])
    with pytest.raises(KeyError):
        _ = c["a"]

