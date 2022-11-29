import superconfig.loaders as loaders


def test_expected_types_defined():
    _ = loaders.Format.Ini
    _ = loaders.Format.Json
    _ = loaders.Format.Properties
    _ = loaders.Format.Toml
    _ = loaders.Format.Yaml
