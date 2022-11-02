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

