"""The high level interface for building config trees."""
from typing import Tuple, Any

from superconfig import aws
from superconfig import converters
from superconfig import formats
from superconfig import config
from superconfig import loaders
from superconfig import misc
from superconfig import gtrs
from superconfig import statics
from superconfig import let


def config_stack(*args, context=None):
    layers = []
    for x in args:
        if isinstance(x, dict):
            layers.append(gtrs.GetterLayer(x))
        else:
            layers.append(x)
    return config.layered_config(context or config.Context(), layers)


def aws_parameter_store_layer(
        parameter_store_base_path,
        refresh_interval_s=gtrs.constant(60),
        retry_interval_s=gtrs.constant(10),
        ttl_s=gtrs.constant(30),
        negative_ttl_s=gtrs.constant(10),
        is_enabled=None,
):
    return gtrs.GetterAsLayer(
        aws_parameter_store_getter(
            parameter_store_base_path=parameter_store_base_path,
            refresh_interval_s=refresh_interval_s,
            retry_interval_s=retry_interval_s,
            ttl_s=ttl_s,
            negative_ttl_s=negative_ttl_s,
            is_enabled=None if is_enabled is None else let.compile(is_enabled),
        )
    )


def aws_parameter_store_getter(
    parameter_store_base_path=None,
    binary_decoder=None,
    refresh_interval_s=gtrs.constant(60),
    retry_interval_s=gtrs.constant(10),
    ttl_s=gtrs.constant(30),
    negative_ttl_s=gtrs.constant(10),
    is_enabled=None,
):
    return gtrs.CacheGetter(
        loaders.AutoRefreshGetter(
            layer_constructor=gtrs.IndexGetterLayer,
            fetcher=aws.AwsParameterStoreFetcher(
                root=parameter_store_base_path,
                binary_decoder=binary_decoder
            ),
            refresh_interval_s=refresh_interval_s,
            retry_interval_s=retry_interval_s,
            is_enabled=None if is_enabled is None else let.compile(is_enabled),
        ),
        ttl_s=ttl_s,
        negative_ttl_s=negative_ttl_s,
    )


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
# config = layer_config(
#     [
#         cache_layer(ttl_s=30, neg_ttl_s=10),
#         {"db.conn.*.*": sqlalchemy_connection_graft(config_key="db.conn.{1}.{2}")},
#         file_layer(name="{env.user}/.config/overrides.json", refresh_s=from_key("{config.refresh}")),
#         {"db.conn.*.*": aws_secretsmanager(name="db.conn.{env}.{1}.{2}", format=format.Json)},
#         aws_parameter_store_layer(prefix="/{env}/app", ttl_s=30, neg_ttl_s=10, refresh_s=60),
#         file_layer(filename="{env.config.sops}", refresh_s=60),
#         file_layer(filename="{env.config}", refresh_s=60),
#         file_layer(filename="{env.config.common}", refresh_s=60),
#         {
#             "env.config.common": value(
#                 envars=["APP_CONFIG_COMMON"],
#                 default="{project_root}/config/config.[yaml|json]"
#             ),
#             "env.config": value(
#                 envars=["APP_CONFIG"],
#                 default="{project_root}/config/{env}/config.[yaml|json]"
#             ),
#             "env.config.sops": value(
#                 envars=["APP_CONFIG_SOPS"],
#                 default="{project_root}/config/{env}/secrets.enc"
#             ),
#         }, {
#             "env.user": username(),
#             "env.root": function(your_project_root_function),
#             "env": envar(envars=["APP_ENV", "ENV"], required=True)
#             "config.refresh": value(envars=["APP_OVERRIDE_REFRESH"], default=30, transform=int)
#             "aws.enabled": constant(False),
#         },
#         )
#     ]
# )
#

class NoDefault:
    pass


def value(
    transform=None,
    envar=None,
    envars=None,
    env_transform=None,
    default=NoDefault,
    stop=False,
    expand_result=False,
):
    if stop and default != NoDefault:
        raise ValueError("default and stop are mutually incompatible")
    if envars is None:
        envars = []
    if envar is not None:
        envars = [envar] + envars
    getters = []
    for env in envars:
        getters.append(gtrs.Env(env))
    if env_transform:
        getters = [gtrs.Transform(env_transform, gtrs.GetterStack(getters))]
    getters.append(gtrs.BaseKeyReference())
    if default != NoDefault:
        getters.append(gtrs.Constant(default))
    elif stop:
        getters.append(gtrs.Stop)
    else:
        getters.append(gtrs.NotFound)
    v = gtrs.GetterStack(getters)
    if expand_result:
        v = gtrs.ExpansionGetter(v)
    if transform is not None:
        v = gtrs.Transform(transform, v)
    return v


def file_layer(
    filename,  # Can be: "foo" "{oo}" GETTER Key()
    layer_constructor=None,
    is_enabled=None,
    refresh_interval_s=30,  # Can be: int "{}" GETTER Key()
    retry_interval_s=10,
):
    return FileLayerLoader(
        filename=let.compile(filename),
        layer_constructor=layer_constructor,
        is_enabled=None if is_enabled is None else let.compile(is_enabled),
        refresh_interval_s=let.compile(refresh_interval_s),
        retry_interval_s=let.compile(retry_interval_s),
    )


class FileLayerLoader:
    def __init__(
            self,
            filename,
            layer_constructor,
            refresh_interval_s=gtrs.constant(10),
            retry_interval_s=gtrs.constant(5),
            is_enabled=None,
            reader=loaders.simple_reader,
            clear_on_removal=False,
            clear_on_fetch_failure=False,
            clear_on_load_failure=False,
    ):
        self.file_fetcher = loaders.FileFetcher(filename, reader=reader)
        self.layer_constructor = layer_constructor or dynamic_layer_constructor(self.file_fetcher)
        self.auto_loader = loaders.AutoRefreshGetter(
            layer_constructor=self.layer_constructor,
            fetcher=self.file_fetcher,
            refresh_interval_s=refresh_interval_s,
            retry_interval_s=retry_interval_s,
            is_enabled=is_enabled,
            clear_on_removal=clear_on_removal,
            clear_on_fetch_failure=clear_on_fetch_failure,
            clear_on_load_failure=clear_on_load_failure,
        )

    def get_item(self, key, context, lower_layer: config.Layer) -> Tuple[int, int, Any | None]:
        return self.auto_loader.read("", key.split("."), context, lower_layer)


def dynamic_layer_constructor(obj_with_filename):

    # noinspection PyShadowingNames
    def _wrapped(data, obj_with_filename=obj_with_filename):
        layer_constructor = formats.layer_constructor_for_filename(obj_with_filename.filename)
        return layer_constructor(data)

    return _wrapped


def aws_secretsmanager_getter(
        name=None,
        format=None,
        stage=None,
        binary_decoder=None,
):
    if format is None:
        layer_constructor = gtrs.constant
    else:
        layer_constructor=formats.layer_constructor_for_format(format)
    return loaders.AutoRefreshGetter(
        layer_constructor=layer_constructor,
        fetcher=aws.SecretsManagerFetcher(
            name=None if name is None else let.compile(name),
            stage=stage,
            binary_decoder=binary_decoder,
        )
    )


class Decoders:
    base64 = converters.bytes_from_base64


def username():
    return misc.UsernameGetter()


def homedir():
    return misc.HomedDirGetter()


def sops_layer(
    filename,
    sops_args=None,
    is_enabled=None,
    refresh_interval_s=gtrs.constant(10),
    retry_interval_s=gtrs.constant(5),
):
    return FileLayerLoader(
        filename=let.compile(filename),
        reader=lambda x, sops_args=sops_args: loaders.sops_reader(x, sops_args),
        layer_constructor=lambda x: statics.ObjLayer(converters.obj_from_yaml(x)),
        is_enabled=None if is_enabled is None else let.compile(is_enabled),
        refresh_interval_s=let.compile(refresh_interval_s),
        retry_interval_s=let.compile(retry_interval_s),
    )


def cache(getter, ttl_s=gtrs.constant(60), negative_ttl_s=gtrs.constant(30)):
    return gtrs.CacheGetter(
        getter,
        ttl_s=let.compile(ttl_s),
        negative_ttl_s=let.compile(negative_ttl_s))

