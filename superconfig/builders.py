"""The high level interface for building config trees."""

from . import smarts
from . import loaders


def parameter_store_getter(
    parameter_store_base_path=None,
    refresh_interval_s=60,
    retry_interval_s=10,
):
    return smarts.CacheGetter(
        loaders.AutoRefreshGetter(
            layer_constructor=smarts.IndexGetterLayer,
            fetcher=loaders.AwsParameterStoreFetcher(root=parameter_store_base_path),
            refresh_interval_s=refresh_interval_s,
            retry_interval_s=retry_interval_s,
        )
    )


# def parameter_store_layer():
#     pass
#
#
# def parameter_store_graft():
#     pass
#
#
# def file_layer(format=Json|Yaml|Ini|Toml|Properties):
#     pass
#
#
# def secrets_manager_getter(
#     format=Json|Yaml|Ini|Toml|Properties|String
# ):
#     pass
#
#
# def secrets_manager_graft(
#         format=Json|Yaml|Ini|Toml|Properties|String
# ):
#     pass
#
#
# def value(name=None, names=None, default=None, stop=True, transform=None):
#     pass
#
#
# def transform(f):
#     pass
#
#
# def cache_layer():
#     pass
#
#
# def sqlalchemy_connection_graft():
#     """A level of SQLalchemy connections"""
#     pass
#
#
# def graft(layers=[]):
#     pass
#
#
# config =layer_config(
#     [
#         cache_layer(ttl_s=30, neg_ttl_s=10),
#         smart_layer(
#             {
#                 "db.conn.*.*": sqlalchemy_connection_graft(config_key="db.conn.{1}.{2}"),
#             }
#         ),
#         file_layer(name="{env.user}/.config/overrides.json", refresh_s=from_key("{config.refresh}")),
#         smart_layer(
#             {
#                 "db.conn.*.*": aws_secrets_manager_graft(name="db.conn.{env}.{1}.{2}", kind=format.Json)
#             }
#         ),
#         aws_parameter_store_layer(prefix="/{env}/app", ttl_s=30, neg_ttl_s=10, refresh_s=60),
#         file_layer(filename="{env.config.sops}", refresh_s=60),
#         file_layer(filename="{env.config}", refresh_s=60),
#         file_layer(filename="{env.config.common}", refresh_s=60),
#         smart_layer(
#             {
#                 "env.config.common": value(
#                     envars=["APP_CONFIG_COMMON"],
#                     default=expansion("{project_root}/config/config.[yaml|json]")
#                 )
#                 "env.config": value(
#                     envars=["APP_CONFIG"],
#                     default=expansion("{project_root}/config/{env}/config.[yaml|json]")
#                 )
#                 "env.config.sops": value(
#                     envars=["APP_CONFIG_SOPS"],
#                     default=expansion("{project_root}/config/{env}/secrets.enc")
#                 )
#             }
#         ),
#         smart_layer(
#             {
#                 "env.user": username(),
#                 "env.root": project_root(),
#                 "env": envar(envars=["APP_ENV", "ENV"], required=True)
#                 "config.refresh": value(envars=["APP_OVERRIDE_REFRESH"], default=30, transform=int)
#                 "aws.enabled": constant(False),
#             }
#         ),
#         )
#     ]
# )


