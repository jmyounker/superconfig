import datetime
import json

import freezegun
import pytest

from .helpers import is_expected_getitem
from superconfig import config
from superconfig import converters
from superconfig import builders
from superconfig import loaders
from superconfig import gtrs
from superconfig import statics
from superconfig import let

def test_get_constant_leaf():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.Constant(5)
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5


def test_node_intercepts_descendants():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.Constant(5)
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5
    assert c["a.b.c"] == 5


def test_node_hides_leaf():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.Constant(5)
    s["a.b.c"] = gtrs.Constant(6)
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5
    assert c["a.b.c"] == 5


def test_node_without_result_continues():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.NotFound()
    s["a.b.c"] = gtrs.Constant(6)
    c = config.Config(config.Context(), s)
    assert c["a.b.c"] == 6


def test_env_getter_with_missing_envar(monkeypatch):
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.Env("AB")
    c = config.Config(config.Context(), s)
    monkeypatch.delenv("AB", raising=False)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_env_getter_with_envar(monkeypatch):
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.Env("AB")
    c = config.Config(config.Context(), s)
    monkeypatch.setenv("AB", "")
    assert c["a.b"] == ""
    monkeypatch.setenv("AB", "foo")
    assert c["a.b"] == "foo"


def test_getter_stack_empty_is_not_found():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.GetterStack([])
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_getter_stack_with_one_works():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.GetterStack([gtrs.Constant(5)])
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 5


def test_getter_stack_first_found_blocks():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.GetterStack([gtrs.Constant(5), gtrs.Constant(6)])
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 5


def test_getter_stack_continues_if_not_found():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.GetterStack([gtrs.NotFound(), gtrs.Constant(6)])
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 6


def test_how_to_make_envar_with_default(monkeypatch):
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.GetterStack([gtrs.Env("AB"), gtrs.Constant(6)])
    c = config.Config(config.Context(), s)
    monkeypatch.setenv("AB", "foo")
    assert c["a.b"] == "foo"
    monkeypatch.delenv("AB")
    assert c["a.b"] == 6


def test_how_to_make_a_fail_immediately_if_not_found(monkeypatch):
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.GetterStack([gtrs.Env("AB"), gtrs.Stop()])
    s["a.b.c"] = gtrs.Constant(6)
    c = config.Config(config.Context(), s)
    monkeypatch.setenv("AB", "foo")
    assert c["a.b.c"] == "foo"
    monkeypatch.delenv("AB")
    with pytest.raises(KeyError):
        _ = c["a.b.c"]


def test_transform_on_found():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.Transform(f=int, getter=gtrs.Constant("5"))
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 5


def test_transform_on_not_found_is_not_found():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.Transform(f=int, getter=gtrs.NotFound())
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_transform_failure():
    s = gtrs.SmartLayer()

    class Oops(Exception):
        pass

    def oops(x):
        raise Oops
    s["a.b"] = gtrs.Transform(f=oops, getter=gtrs.Constant(5))
    c = config.Config(config.Context(), s)
    with pytest.raises(ValueError):
        _ = c["a.b"]
    with pytest.raises(ValueError):
        _ = c.get("a.b")


def test_ignore_transform_failure():
    s = gtrs.SmartLayer()

    class Oops(Exception):
        pass

    def oops(x):
        raise Oops
    s["a.b"] = gtrs.IgnoreTransformErrors(gtrs.Transform(f=oops, getter=gtrs.Constant(5)))
    c = config.Config(config.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a.b"]


def test_how_to_default_when_transform_fails():
    s = gtrs.SmartLayer()

    class Oops(Exception):
        pass

    def oops(x):
        raise Oops
    s["a.b"] = gtrs.GetterStack(
        [
            gtrs.IgnoreTransformErrors(gtrs.Transform(f=oops, getter=gtrs.Constant(5))),
            gtrs.Constant(6),
        ]
    )
    c = config.Config(config.Context(), s)
    assert c["a.b"] == 6


def test_expansion_layer():
    c = config.layered_config(config.Context(), [
            gtrs.KeyExpansionLayer(),
            gtrs.SmartLayer(
                {
                    "a.foo.bar.foo.b": gtrs.Constant(1),
                    "a.foo.baz.foo.b": gtrs.Constant(2),
                },
            ),
            gtrs.SmartLayer({}),
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
            gtrs.SmartLayer({
                "a": gtrs.Graft(statics.ObjLayer({"b": 1, "c": 2})),
                "a.b.d": gtrs.Constant(4)
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
            gtrs.CacheLayer(ttl_s=gtrs.constant(ttl_s)),
            gtrs.SmartLayer({
                "a": gtrs.Counter(0),
            })
        ])
        assert c["a"] == 1
        assert c["a"] == 1


def test_cache_flushes_after_timeout():
    timeout_s = 3
    with freezegun.freeze_time():
        c = config.layered_config(config.Context(), [
            gtrs.CacheLayer(ttl_s=gtrs.constant(timeout_s)),
            gtrs.SmartLayer({
                "a": gtrs.Counter(0),
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
        gtrs.CacheLayer(ttl_s=gtrs.constant(ttl_s)),
        gtrs.SmartLayer({
            "a": gtrs.Counter(0),
            "b": gtrs.Counter(10),
        })
    ])
    now = datetime.datetime.now()
    for (t, samples) in test_cases:
        with freezegun.freeze_time(now + datetime.timedelta(seconds=t)):
            for key, expected_value in samples:
                assert c[key] == expected_value


def test_key_expansion_layer():
    s = gtrs.SmartLayer()
    s["a.b"] = gtrs.Constant(5)
    c = config.layered_config(
        config.Context(),
        [
            gtrs.KeyExpansionLayer(),
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
            gtrs.GetterAsLayer(
                loaders.AutoRefreshGetter(
                    layer_constructor=lambda x: statics.ObjLayer(converters.obj_from_json(converters.string_from_bytes(x))),
                    fetcher=loaders.FileFetcher(let.compile(str(f))),
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
            gtrs.SmartLayer({
                "": loaders.AutoRefreshGetter(
                    layer_constructor=lambda x: statics.ObjLayer(converters.obj_from_json(converters.string_from_bytes(x))),
                    fetcher=loaders.FileFetcher(let.compile(str(f))),
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
            [gtrs.SmartLayer(getters)],
        )
        assert is_expected_getitem(c, key, expected_value)
