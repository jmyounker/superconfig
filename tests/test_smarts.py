import pytest

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
