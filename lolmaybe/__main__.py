import tempfile

import click

import utils
from astpasses import ASTProcess
from astpasses.extract_variables import ExtractVariables
from astpasses.replace_variables import ReplaceVariableNames
from llm import UnderstandCode

from defaults import HOST, MODEL


@click.command()
@click.option('--filename', default='/dev/stdin')
@click.option('--model', default=MODEL)
@click.option('--host', default=HOST)
def main(filename, model, host):
    with open(filename, 'r') as f:
        base = f.read()

    data = utils.wrap_code(base)

    # write to a tempfile to use the ASTProcess
    with tempfile.NamedTemporaryFile() as fp:
        fp.write(bytes(data, encoding='utf-8'))
        fp.flush()

        astp = ASTProcess(fp.name)

    func_info = astp.run(ExtractVariables())

    # Should only be one function defined
    uc = UnderstandCode(base, model=model, host=host)

    print(f'/* {uc.get_summary().strip()} */')

    new_names = {}

    for func, definition in func_info.items():
        to_rename = {}
        seen_before = set()

        for arg, typedef in definition['arguments'].items():
            new = uc.suggest_new_variable_name(arg, ' '.join(typedef))
            new_name = utils.normalize_name(new.get('new_name', arg))
            new_name = utils.make_uniq(new_name, seen_before)
            seen_before.add(new_name)
            to_rename[arg] = new_name
            print(f'/* {arg} -> {new_name} */')

        for var, typedef in definition['variables'].items():
            new = uc.suggest_new_variable_name(var, ' '.join(typedef))
            new_name = utils.normalize_name(new.get('new_name', var))
            new_name = utils.make_uniq(new_name, seen_before)
            seen_before.add(new_name)
            to_rename[var] = new_name
            print(f'/* {var} -> {new_name} */')

        new_names[func] = to_rename

    # modify the AST to use the new names
    astp.run(ReplaceVariableNames(new_names))

    print(astp.get_str())


if __name__ == "__main__":
    main()
