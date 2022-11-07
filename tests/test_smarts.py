import datetime
import json

import freezegun
import pytest

from .helpers import is_expected_getitem
import superconfig as sc


def test_get_constant_leaf():
    s = sc.SmartLayer()
    s["a.b"] = sc.Constant(5)
    c = sc.Config(sc.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5


def test_node_intercepts_descendants():
    s = sc.SmartLayer()
    s["a.b"] = sc.Constant(5)
    c = sc.Config(sc.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5
    assert c["a.b.c"] == 5


def test_node_hides_leaf():
    s = sc.SmartLayer()
    s["a.b"] = sc.Constant(5)
    s["a.b.c"] = sc.Constant(6)
    c = sc.Config(sc.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5
    assert c["a.b.c"] == 5


def test_node_without_result_continues():
    s = sc.SmartLayer()
    s["a.b"] = sc.NotFound()
    s["a.b.c"] = sc.Constant(6)
    c = sc.Config(sc.Context(), s)
    assert c["a.b.c"] == 6


def test_env_getter_with_missing_envar(monkeypatch):
    s = sc.SmartLayer()
    s["a.b"] = sc.Env("AB")
    c = sc.Config(sc.Context(), s)
    monkeypatch.delenv("AB", raising=False)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_env_getter_with_envar(monkeypatch):
    s = sc.SmartLayer()
    s["a.b"] = sc.Env("AB")
    c = sc.Config(sc.Context(), s)
    monkeypatch.setenv("AB", "")
    assert c["a.b"] == ""
    monkeypatch.setenv("AB", "foo")
    assert c["a.b"] == "foo"


def test_getter_stack_empty_is_not_found():
    s = sc.SmartLayer()
    s["a.b"] = sc.GetterStack([])
    c = sc.Config(sc.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_getter_stack_with_one_works():
    s = sc.SmartLayer()
    s["a.b"] = sc.GetterStack([sc.Constant(5)])
    c = sc.Config(sc.Context(), s)
    assert c["a.b"] == 5


def test_getter_stack_first_found_blocks():
    s = sc.SmartLayer()
    s["a.b"] = sc.GetterStack([sc.Constant(5), sc.Constant(6)])
    c = sc.Config(sc.Context(), s)
    assert c["a.b"] == 5


def test_getter_stack_continues_if_not_found():
    s = sc.SmartLayer()
    s["a.b"] = sc.GetterStack([sc.NotFound(), sc.Constant(6)])
    c = sc.Config(sc.Context(), s)
    assert c["a.b"] == 6


def test_how_to_make_envar_with_default(monkeypatch):
    s = sc.SmartLayer()
    s["a.b"] = sc.GetterStack([sc.Env("AB"), sc.Constant(6)])
    c = sc.Config(sc.Context(), s)
    monkeypatch.setenv("AB", "foo")
    assert c["a.b"] == "foo"
    monkeypatch.delenv("AB")
    assert c["a.b"] == 6


def test_how_to_make_a_fail_immediately_if_not_found(monkeypatch):
    s = sc.SmartLayer()
    s["a.b"] = sc.GetterStack([sc.Env("AB"), sc.Stop()])
    s["a.b.c"] = sc.Constant(6)
    c = sc.Config(sc.Context(), s)
    monkeypatch.setenv("AB", "foo")
    assert c["a.b.c"] == "foo"
    monkeypatch.delenv("AB")
    with pytest.raises(KeyError):
        _ = c["a.b.c"]


def test_transform_on_found():
    s = sc.SmartLayer()
    s["a.b"] = sc.Transform(f=int, getter=sc.Constant("5"))
    c = sc.Config(sc.Context(), s)
    assert c["a.b"] == 5


def test_transform_on_not_found_is_not_found():
    s = sc.SmartLayer()
    s["a.b"] = sc.Transform(f=int, getter=sc.NotFound())
    c = sc.Config(sc.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_transform_failure():
    s = sc.SmartLayer()

    class Oops(Exception):
        pass

    def oops(x):
        raise Oops
    s["a.b"] = sc.Transform(f=oops, getter=sc.Constant(5))
    c = sc.Config(sc.Context(), s)
    with pytest.raises(ValueError):
        _ = c["a.b"]
    with pytest.raises(ValueError):
        _ = c.get("a.b")


def test_ignore_transform_failure():
    s = sc.SmartLayer()

    class Oops(Exception):
        pass

    def oops(x):
        raise Oops
    s["a.b"] = sc.IgnoreTransformErrors(sc.Transform(f=oops, getter=sc.Constant(5)))
    c = sc.Config(sc.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_how_to_default_when_transform_fails():
    s = sc.SmartLayer()

    class Oops(Exception):
        pass

    def oops(x):
        raise Oops
    s["a.b"] = sc.GetterStack(
        [
            sc.IgnoreTransformErrors(sc.Transform(f=oops, getter=sc.Constant(5))),
            sc.Constant(6),
        ]
    )
    c = sc.Config(sc.Context(), s)
    assert c["a.b"] == 6


def test_expansion_layer():
    c = sc.layered_config(sc.Context(), [
            sc.KeyExpansionLayer(),
            sc.SmartLayer(
                {
                    "a.foo.bar.foo.b": sc.Constant(1),
                    "a.foo.baz.foo.b": sc.Constant(2),
                },
            ),
            sc.SmartLayer({}),
            sc.JsonLayer({"f": "foo", "g": "bar", "h": { "i": "baz"}}),
        ]
    )
    for k, res in [
        ("a.{f}.{g}.{f}.b", 1),
        ("a.{f}.{h.i}.{f}.b", 2),
        ("a.{q}", KeyError),
    ]:
        assert is_expected_getitem(c, k, res)


def test_graft():
    c = sc.layered_config(sc.Context(), [
            sc.SmartLayer({
                "a": sc.Graft(sc.JsonLayer({"b": 1, "c": 2})),
                "a.b.d": sc.Constant(4)
            }),
        ]
    )
    for k, res in [
        ("a.b.d", KeyError),
        ("a.b", 1),
    ]:
        assert is_expected_getitem(c, k, res)


def test_cache_caches_records():
    timeout_s = 5
    with freezegun.freeze_time():
        c = sc.layered_config(sc.Context(), [
            sc.CacheLayer(timeout_s=timeout_s),
            sc.SmartLayer({
                "a": sc.Counter(0),
            })
        ])
        assert c["a"] == 1
        assert c["a"] == 1


def test_cache_flushes_after_timeout():
    timeout_s = 5
    with freezegun.freeze_time():
        c = sc.layered_config(sc.Context(), [
            sc.CacheLayer(timeout_s=timeout_s),
            sc.SmartLayer({
                "a": sc.Counter(0),
            })
        ])
        assert c["a"] == 1
        now = datetime.datetime.now()
    with freezegun.freeze_time(now + datetime.timedelta(seconds=timeout_s+1)):
        assert c["a"] == 2


def test_cache_records_have_distinct_expirations():
    timeout_s = 5
    test_cases = [
        (0, [("a", 1)]),
        (2, [("a", 1), ("b", 11)]),
        (3, [("a", 1), ("b", 11)]),
        (6, [("a", 2), ("b", 11)]),
        (9, [("a", 2), ("b", 12)]),
    ]
    c = sc.layered_config(sc.Context(), [
        sc.CacheLayer(timeout_s=timeout_s),
        sc.SmartLayer({
            "a": sc.Counter(0),
            "b": sc.Counter(10),
        })
    ])
    now = datetime.datetime.now()
    for (t, samples) in test_cases:
        with freezegun.freeze_time(now + datetime.timedelta(seconds=t)):
            for key, expected_value in samples:
                assert c[key] == expected_value


def test_file_load_layer_file_missing(tmp_path):
    c = sc.layered_config([sc.LayerLoader(sc.JsonLayer.from_file, str(tmp_path / "foo.json"))])
    with pytest.raises(KeyError):
        _ = c["a"]


def test_file_load_layer_loads_files(tmp_path):
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [sc.LayerLoader(sc.JsonLayer.from_file, str(f))])
    assert c["a"] == 1


def test_file_load_layer_does_not_reload_during_cache_period(tmp_path):
    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.LayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            check_period_s=check_period_s,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        f.write_text(json.dumps({"a": 2}))
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s-1)):
        assert c["a"] == 1


def test_file_load_layer_does_not_load_unchanged_files(tmp_path):
    loaded = [False]

    def load_checking_loader(f):
        loaded[0] = True
        return sc.JsonLayer.from_file(f)

    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.LayerLoader(
            load_checking_loader,
            str(f),
            check_period_s=check_period_s,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        assert loaded[0]
        loaded[0] = False
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s+1)):
        assert c["a"] == 1
        assert not loaded[0]


def test_file_load_layer_loads_changed_files_after_cache_period(tmp_path):
    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.LayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            check_period_s=check_period_s,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        f.write_text(json.dumps({"a": 2}))
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s+1)):
        assert c["a"] == 2


def test_file_load_layer_w_clear_clears_config_after_file_removed(tmp_path):
    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.LayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            check_period_s=check_period_s,
            clear_on_not_found=True,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        f.unlink()
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s+1)):
        with pytest.raises(KeyError):
            _ = c["a"]


def test_file_load_layer_wo_clear_keeps_config_after_file_removal(tmp_path):
    check_period_s = 3
    now = datetime.datetime.now()
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1}))
    c = sc.layered_config(sc.Context(), [
        sc.LayerLoader(
            sc.JsonLayer.from_file,
            str(f),
            check_period_s=check_period_s,
        )])
    with freezegun.freeze_time(now):
        assert c["a"] == 1
        f.unlink()
    with freezegun.freeze_time(now + datetime.timedelta(seconds=check_period_s+1)):
        assert c["a"] == 1
