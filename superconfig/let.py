"""Vars are functions with the signature f(context, lower_layer) -> Any

They are expressions that reference lower layers in the config. They
can be literals, expansions, or direct references to other config
keys.

"""

import config
import helpers
import gtrs


def compile(x):
    if isinstance(x, int):
        return gtrs.constant(x)
    if isinstance(x, str):
        expansions = helpers.expansions(x)
        if not expansions:
            return gtrs.constant(x)

        # noinspection PyShadowingNames
        def f(context, lower_layer, x=x, expansions=expansions):
            return helpers.expand(x, expansions, context, lower_layer)
        return f
    elif isinstance(x, Key):
        expansions = helpers.expansions(x.key)
        if not expansions:
            return gtrs.config_value_constant_key(x.key)

        # noinspection PyShadowingNames
        def f(context, lower_layer, key=x.key, expansions=expansions):
            target_key = helpers.expand(key, expansions, context, lower_layer)
            resp = lower_layer.get_item(target_key, context, config.NullConfig)
            if not resp.found:
                raise KeyError()
            return resp.value
        return f

    elif isinstance(x, gtrs.Getter):
        return gtrs.via(x)

    else:
        return gtrs.constant(x)


class Key:
    def __init__(self, key):
        self.key = key


class Exp:
    def __init__(self, exp):
        self.exp = exp
