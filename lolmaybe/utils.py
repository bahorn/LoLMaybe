import re


def process_radare2_symbols(data):
    """
    can't use radare2's default symbol names as they include dots, which aren't
    valid in C names so the C parser we are using errors out.
    Doing some mangling to resolve that, might break in some cases.
    """
    res = data
    to_replace = [
        '_obj.', ('sym.imp.', ''), ('sym.', ''), 'fcn.'
    ]
    for prefix in to_replace:
        if not isinstance(prefix, tuple):
            findme = prefix
            new = prefix.replace('.', '__dot__')
        else:
            findme = prefix[0]
            new = prefix[1]
        res = res.replace(findme, new)
    return res


def normalize_name(name):
    return re.sub('[^A-Za-z0-9_]+', '_', name)


def make_uniq(name, existing):
    base = name
    new_name = name
    i = 0

    while new_name in existing:
        new_name = f'{base}_{i}'
        i += 1
    return new_name
