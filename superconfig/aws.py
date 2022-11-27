import contextlib

import boto3

import config
import helpers
import loaders
import superconfig


class AwsParameterStoreFetcher(loaders.AbstractFetcher):
    """Pulls parameters from AWS parameterstore.

    Parameter Store has options for the kind of data stored, and how it is
    looked up.

    It seems that parameter stores are treated as trees now, and each node
    contains a single value rather than sets of values.

    It's quite possible that this design is wrong. Instead I should have
    an entire layer that caches each parameter independently, and then
    makes it looks like a normal graft.

    Value parsing then happens with transformers in a higher layer, or within
    a smart layer above the parameter store within the graft.  Actually, thinking
    about it, I can probably rely on a cache layer to handle loading since I'm
    pulling key-by-key.

    That means I don't even need to use fetchers since the fields map
    directly to the cache layer.

    """
    def __init__(self, root=None, client=None):
        self._client = client
        self._root = None if root is None else helpers.ExpandableString(root)

    @contextlib.contextmanager
    def load(self, now, key, rest, context, lower_layer):
        yield self.parameter_tree(self.get_client(), self.name(key, context, lower_layer))

    def get_client(self):
        if self._client:
            return self._client
        return boto3.client("ssm")

    def name(self, key, context, lower_layer):
        if self._root is None:
            return "/" + "/".join(key.split("."))
        return self._root.expand(context, lower_layer)

    def parameter_tree(self, client, path):
        tree = {}
        for k, p in self.describe_parameters_with_keys(client, path):
            tree[k] = ParameterNode(client, p)
        return tree

    def describe_parameters_with_keys(self, client, path):
        for p in self.describe_parameters(client, path):
            key = p["Name"][len(path):].strip("/").replace("/", ".")
            yield (key, p)

    @staticmethod
    def describe_parameters(client, path):
        paginator = client.get_paginator('describe_parameters')
        pager = paginator.paginate(
            ParameterFilters=[
                dict(Key="Path", Option="Recursive", Values=[path])
            ]
        )
        for page in pager:
            for p in page['Parameters']:
                yield p


class ParameterNode:
    def __init__(self, client, parameter):
        self.client = client
        self.parameter = parameter

    def read(self, key, rest, context, lower_layer):
        # noinspection PyBroadException
        try:
            resp = self.client.get_parameter(Name=self.parameter["Name"])
            p = resp["Parameter"]
        except Exception:
            return config.Response.not_found_next
        if p["Type"] == "String":
            return config.Response.found_next(p["Value"])
        elif p["Type"] == "StringList":
            return config.Response.found_next(p["Value"].split(","))
        elif p["Type"] == "SecureString":
            return config.Response.found_next(p["Value"])
        else:
            return config.Response.not_found_next


class SecretsManagerFetcher(loaders.AbstractFetcher):
    def __init__(self, name=None, client=None, stage=None):
        self._client = client
        self._name = None if name is None else helpers.ExpandableString(name)
        self._stage = stage

    @contextlib.contextmanager
    def load(self, now, key, rest, context, lower_layer):
        try:
            yield self.value_from_secret(
                self.get_secret(
                    self.get_client(),
                    self.name(key, context, lower_layer),
                    self.stage()))
        except Exception as e:
            raise superconfig.FetchFailure()

    def get_client(self):
        if self._client:
            return self._client
        return boto3.client("secretsmanager")

    def name(self, key, context, lower_layer):
        if self._name is None:
            return key
        return self._name.expand(context, lower_layer)

    def stage(self):
        return self._stage

    @staticmethod
    def get_secret(client, name, stage):
        kwargs = {'SecretId': name}
        if stage is not None:
            kwargs['VersionStage'] = stage
        try:
            return client.get_secret_value(**kwargs)
        except Exception as e:
            raise superconfig.FetchFailure()

    @staticmethod
    def value_from_secret(secret):
        if 'SecretString' in secret:
            return bytes(secret['SecretString'].encode('utf8'))
        elif 'SecretBinary' in secret:
            return secret['SecretBinary']
        else:
            raise superconfig.FetchFailure("cannot extract value: neither SecretString nor SecretBinary found")


def config_switch(enable_key, default=False):
    def _config_switch(key, rest, context, lower_layer, enable_key=enable_key, default=default):
        resp = lower_layer.get_item(enable_key, context, config.NullLayer)
        if resp.is_found:
            return bool(resp.value)
        else:
            return default
    return _config_switch
