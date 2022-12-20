import re
from typing import AnyStr
from typing import Optional

import config


class ExpandableString:
    def __init__(self, name):
        self.name = name
        self.expansions = expansions(name)

    def expand(self, context: config.Context, lower_layer: config.Layer) -> Optional[AnyStr]:
        return expand(self.name, self.expansions, context, lower_layer)


expansions_ptrn = re.compile(r"\{([^}]+)}")


def expansions(tmpl):
    return set(expansions_ptrn.findall(tmpl))


_is_digit = re.compile(r"\d+")


def expand(tmpl, expansions, context: config.Context, lower_layer: config.Layer) -> Optional[AnyStr]:
    replacements = []
    for exp in expansions:
        if _is_digit.match(exp):
            if not context.globs:
                return None
            if exp not in context.globs:
                return None
            replacements.append(('{%s}' % exp, context.globs[exp]))
        else:
            resp = lower_layer.get_item(exp, context, config.NullLayer)
            if not resp.is_found:
                return None
            replacements.append(('{%s}' % exp, resp.value))
    t = tmpl
    for exp, v in replacements:
        t = t.replace(exp, v)
    return t
