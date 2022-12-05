from superconfig import formats


def test_expected_types_defined():
    _ = formats.Format.Ini
    _ = formats.Format.Json
    _ = formats.Format.Properties
    _ = formats.Format.Toml
    _ = formats.Format.Yaml
