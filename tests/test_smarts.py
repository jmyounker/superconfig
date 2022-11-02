import pytest

import superconfig as sc


def test_get_constant():
    s = sc.SmartLayer()
    s["a.b"] = sc.Constant(5)
    c = sc.Config(sc.Context(), s)
    with pytest.raises(KeyError):
        _ = c["a"]
    assert c["a.b"] == 5