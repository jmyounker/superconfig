import datetime
import json

import freezegun
import pytest

from .helpers import is_expected_getitem
from superconfig import config
from superconfig import converters
from superconfig import builders
from superconfig import loaders
from superconfig import smarts
from superconfig import statics
from superconfig import vars

def test_get_constant_leaf():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.Constant(5)
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5


def test_node_intercepts_descendants():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.Constant(5)
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5
    assert c["a.b.c"] == 5


def test_node_hides_leaf():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.Constant(5)
    s["a.b.c"] = smarts.Constant(6)
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5
    assert c["a.b.c"] == 5


def test_node_without_result_continues():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.NotFound()
    s["a.b.c"] = smarts.Constant(6)
    c = config.Config(config.Context(), s)
    assert c["a.b.c"] == 6


def test_env_getter_with_missing_envar(monkeypatch):
    s = smarts.SmartLayer()
    s["a.b"] = smarts.Env("AB")
    c = config.Config(config.Context(), s)
    monkeypatch.delenv("AB", raising=False)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_env_getter_with_envar(monkeypatch):
    s = smarts.SmartLayer()
    s["a.b"] = smarts.Env("AB")
    c = config.Config(config.Context(), s)
    monkeypatch.setenv("AB", "")
    assert c["a.b"] == ""
    monkeypatch.setenv("AB", "foo")
    assert c["a.b"] == "foo"


def test_getter_stack_empty_is_not_found():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.GetterStack([])
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_getter_stack_with_one_works():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.GetterStack([smarts.Constant(5)])
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 5


def test_getter_stack_first_found_blocks():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.GetterStack([smarts.Constant(5), smarts.Constant(6)])
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 5


def test_getter_stack_continues_if_not_found():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.GetterStack([smarts.NotFound(), smarts.Constant(6)])
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 6


def test_how_to_make_envar_with_default(monkeypatch):
    s = smarts.SmartLayer()
    s["a.b"] = smarts.GetterStack([smarts.Env("AB"), smarts.Constant(6)])
    c = config.Config(config.Context(), s)
    monkeypatch.setenv("AB", "foo")
    assert c["a.b"] == "foo"
    monkeypatch.delenv("AB")
    assert c["a.b"] == 6


def test_how_to_make_a_fail_immediately_if_not_found(monkeypatch):
    s = smarts.SmartLayer()
    s["a.b"] = smarts.GetterStack([smarts.Env("AB"), smarts.Stop()])
    s["a.b.c"] = smarts.Constant(6)
    c = config.Config(config.Context(), s)
    monkeypatch.setenv("AB", "foo")
    assert c["a.b.c"] == "foo"
    monkeypatch.delenv("AB")
    with pytest.raises(KeyError):
        _ = c["a.b.c"]


def test_transform_on_found():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.Transform(f=int, getter=smarts.Constant("5"))
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 5


def test_transform_on_not_found_is_not_found():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.Transform(f=int, getter=smarts.NotFound())
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_transform_failure():
    s = smarts.SmartLayer()

    class Oops(Exception):
        pass

    def oops(x):
        raise Oops
    s["a.b"] = smarts.Transform(f=oops, getter=smarts.Constant(5))
    c = config.Config(config.Context(), s)
    with pytest.raises(ValueError):
        _ = c["a.b"]
    with pytest.raises(ValueError):
        _ = c.get("a.b")


def test_ignore_transform_failure():
    s = smarts.SmartLayer()

    class Oops(Exception):
        pass

    def oops(x):
        raise Oops
    s["a.b"] = smarts.IgnoreTransformErrors(smarts.Transform(f=oops, getter=smarts.Constant(5)))
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_how_to_default_when_transform_fails():
    s = smarts.SmartLayer()

    class Oops(Exception):
        pass

    def oops(x):
        raise Oops
    s["a.b"] = smarts.GetterStack(
        [
            smarts.IgnoreTransformErrors(smarts.Transform(f=oops, getter=smarts.Constant(5))),
            smarts.Constant(6),
        ]
    )
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 6


def test_expansion_layer():
    c = config.layered_config(config.Context(), [
            smarts.KeyExpansionLayer(),
            smarts.SmartLayer(
                {
                    "a.foo.bar.foo.b": smarts.Constant(1),
                    "a.foo.baz.foo.b": smarts.Constant(2),
                },
            ),
            smarts.SmartLayer({}),
            statics.ObjLayer({"f": "foo", "g": "bar", "h": {"i": "baz"}}),
        ]
    )
    for k, res in [
        ("a.{f}.{g}.{f}.b", 1),
        ("a.{f}.{h.i}.{f}.b", 2),
        ("a.{q}", KeyError),
    ]:
        assert is_expected_getitem(c, k, res)


def test_graft():
    c = config.layered_config(config.Context(), [
            smarts.SmartLayer({
                "a": smarts.Graft(statics.ObjLayer({"b": 1, "c": 2})),
                "a.b.d": smarts.Constant(4)
            }),
        ]
    )
    for k, res in [
        # ("a.b.d", KeyError),
        ("a.b", 1),
    ]:
        assert is_expected_getitem(c, k, res)


def test_cache_caches_records():
    ttl_s = 5
    with freezegun.freeze_time():
        c = config.layered_config(config.Context(), [
            smarts.CacheLayer(ttl_s=smarts.constant(ttl_s)),
            smarts.SmartLayer({
                "a": smarts.Counter(0),
            })
        ])
        assert c["a"] == 1
        assert c["a"] == 1


def test_cache_flushes_after_timeout():
    timeout_s = 3
    with freezegun.freeze_time():
        c = config.layered_config(config.Context(), [
            smarts.CacheLayer(ttl_s=smarts.constant(timeout_s)),
            smarts.SmartLayer({
                "a": smarts.Counter(0),
            })
        ])
        assert c["a"] == 1
        now = datetime.datetime.now()
    with freezegun.freeze_time(now + datetime.timedelta(seconds=timeout_s + 1)):
        assert c["a"] == 2


def test_cache_records_have_distinct_expirations():
    ttl_s = 5
    test_cases = [
        (0, [("a", 1)]),
        (2, [("a", 1), ("b", 11)]),
        (3, [("a", 1), ("b", 11)]),
        (6, [("a", 2), ("b", 11)]),
        (9, [("a", 2), ("b", 12)]),
    ]
    c = config.layered_config(config.Context(), [
        smarts.CacheLayer(ttl_s=smarts.constant(ttl_s)),
        smarts.SmartLayer({
            "a": smarts.Counter(0),
            "b": smarts.Counter(10),
        })
    ])
    now = datetime.datetime.now()
    for (t, samples) in test_cases:
        with freezegun.freeze_time(now + datetime.timedelta(seconds=t)):
            for key, expected_value in samples:
                assert c[key] == expected_value


def test_key_expansion_layer():
    s = smarts.SmartLayer()
    s["a.b"] = smarts.Constant(5)
    c = config.layered_config(
        config.Context(),
        [
            smarts.KeyExpansionLayer(),
            config.IndexLayer({
                "a.b": 1,
                "env": "b",
            }),
        ]
    )
    assert c["a.{env}"] == 1
    assert c["a.b"] == 1
    assert c["env"] == "b"
    assert is_expected_getitem(c, "{env}", KeyError)


def test_getter_to_layer_adapter(tmp_path):
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1, "b": {"c": 2}}))
    c = config.layered_config(
        config.Context(),
        [
            smarts.GetterAsLayer(
                loaders.AutoRefreshGetter(
                    layer_constructor=lambda x: statics.ObjLayer(converters.obj_from_json(converters.string_from_bytes(x))),
                    fetcher=loaders.FileFetcher(vars.compile(str(f))),
                ),
            ),
        ]
    )
    assert c["a"] == 1
    assert c["b.c"] == 2


def test_smart_layer_root_getter(tmp_path):
    f = tmp_path / "foo.json"
    f.write_text(json.dumps({"a": 1, "b": {"c": 2}}))
    c = config.layered_config(
        config.Context(),
        [
            smarts.SmartLayer({
                "": loaders.AutoRefreshGetter(
                    layer_constructor=lambda x: statics.ObjLayer(converters.obj_from_json(converters.string_from_bytes(x))),
                    fetcher=loaders.FileFetcher(vars.compile(str(f))),
                ),
            }),
        ]
    )
    assert c["a"] == 1
    assert c["b.c"] == 2


def test_matched_pattern_getters():
    class FoundKey:
        def read(self, key, rest, *args, **kwargs):
            return config.Response.found((key, rest))
    test_cases = [
        ({"one": FoundKey()}, "one", ("one", [])),
        ({"one": FoundKey()}, "one.two", ("one", ["two"])),
        ({"{}": FoundKey()}, "one", ("one", [])),
        ({"{}": FoundKey()}, "one.two", ("one", ["two"])),
        ({"{}.{}": FoundKey()}, "one.two", ("one.two", [])),
        ({"{}.{}": FoundKey()}, "one.two.three", ("one.two", ["three"])),
        ({"one.{}": FoundKey()}, "one.two.three", ("one.two", ["three"])),
        ({"{}.two": FoundKey()}, "one.two.three", ("one.two", ["three"])),
        ({"{}.two": FoundKey()}, "one", KeyError),
        ({"{}": builders.value(default="{1}", expand_result=True)}, "one.two", "one"),
        ({"{}.{}": builders.value(default="{2}.{1}", expand_result=True)}, "one.two", "two.one"),
        ({"{}.{}": builders.value(default="{1}.{2}", expand_result=True)}, "one.two.three", "one.two"),
        ({"{}.{}": builders.value(default="{1}.{2}", expand_result=True)}, "one", KeyError),
    ]
    for getters, key, expected_value in test_cases:
        c = config.layered_config(
            config.Context(),
            [smarts.SmartLayer(getters)],
        )
        assert is_expected_getitem(c, key, expected_value)
