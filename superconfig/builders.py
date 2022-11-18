"""The high level interface for building config trees."""

from . import config
from . import loaders


def parameter_store_getter(
    parameter_store_base_path=None,
    refresh_interval_s=60,
    retry_interval_s=10,
):
    return loaders.AutoRefreshGetter(
        layer_constructor=config.IndexLayer,
        fetcher=loaders.AwsParameterStoreFetcher(root=parameter_store_base_path),
        refresh_interval_s=refresh_interval_s,
        retry_interval_s=retry_interval_s,
    )
