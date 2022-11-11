import re
from typing import AnyStr
from typing import Optional

import config


expansions_ptrn = re.compile(r"\{([^}]+)}")


def expansions(tmpl):
    return set(expansions_ptrn.findall(tmpl))


def expand(tmpl, expansions, context: config.Context, lower_layer: config.Layer) -> Optional[AnyStr]:
    replacements = []
    for exp in expansions:
        found, cont, v = lower_layer.get_item(exp, context, config.NullLayer)
        if found == config.ReadResult.NotFound:
            return None
        replacements.append(('{%s}' % exp, v))
    t = tmpl
    for exp, v in replacements:
        t = t.replace(exp, v)
    return t