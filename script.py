import tempfile
import re

import click
import jinja2
from ollama import Client
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from pycparser import c_ast, c_generator, parse_file

MODEL = "deepseek-coder:6.7b"
HOST = 'http://localhost:11434'

templateLoader = jinja2.FileSystemLoader(searchpath="./templates")
templateEnv = jinja2.Environment(loader=templateLoader)


class TypeVisitor(c_ast.NodeVisitor):
    def __init__(self):
        self._found = []
        super().__init__()

    def visit_IdentifierType(self, node):
        self._found = node.names

    def found(self):
        return self._found


class DeclVisitor(c_ast.NodeVisitor):
    def __init__(self):
        self._decls = {}
        super().__init__()

    def visit_Decl(self, node):
        tv = TypeVisitor()
        tv.visit(node)
        self._decls[node.name] = tv.found()

    def decls(self):
        return self._decls


class FuncDefVisitor(c_ast.NodeVisitor):
    def __init__(self):
        self._functions = {}
        super().__init__()

    def visit_FuncDef(self, node):
        # print('%s at %s' % (node.decl.name, node.decl.coord))

        args = {}
        for arg in node.decl.type.args:
            tv = TypeVisitor()
            tv.visit(arg.type)
            if arg.name is None:
                continue
            args[arg.name] = tv.found()

        dv = DeclVisitor()
        dv.visit(node.body)

        self._functions[node.decl.name] = {
            'arguments': args,
            'variables': dv.decls()
        }

    def functions(self):
        return self._functions


def get_func_info(filename):
    """
    Extracting information from the function, using a set of AST traversals.
    """
    # Seems we have to use parse_file() if we want to use the preprocessor,
    # which requires a file on disk.
    ast = parse_file(
        filename,
        use_cpp=True,
        cpp_args=r'-Iutils/fake_libc_include'
    )

    v = FuncDefVisitor()
    v.visit(ast)
    return v.functions()


class ReplacerVisitor(c_ast.NodeVisitor):
    """
    Replace variable names used in a function.
    """

    def __init__(self, new_names):
        self._new_names = new_names
        super().__init__()

    def visit_TypeDecl(self, node):
        if node.declname not in self._new_names:
            return

        node.declname = self._new_names[node.declname]

    def visit_ID(self, node):
        if node.name not in self._new_names:
            return

        node.name = self._new_names[node.name]


class FuncReplacerVisitor(c_ast.NodeVisitor):
    """
    Visit functions, call the replacer on them.
    """

    def __init__(self, new_names):
        self._new_names = new_names
        super().__init__()

    def visit_FuncDef(self, node):
        if node.decl.name not in self._new_names:
            return

        v = ReplacerVisitor(self._new_names[node.decl.name])
        v.visit(node)


class FuncPrint(c_ast.NodeVisitor):
    """
    Just pruning for the typedefs the parser adds.
    """

    def __init__(self):
        super().__init__()
        self._functions = []

    def visit_FuncDef(self, node):
        generator = c_generator.CGenerator()
        self._functions.append(generator.visit(node))

    def functions(self):
        return self._functions


def modify_variable_names(filename, new_names):
    """
    Modify the AST to change the variable names and return the modified code.
    """
    ast = parse_file(
        filename,
        use_cpp=True,
        cpp_args=r'-Iutils/fake_libc_include'
    )
    v = FuncReplacerVisitor(new_names)
    v.visit(ast)

    fp = FuncPrint()
    fp.visit(ast)

    return '\n\n'.join(fp.functions())


class NewVariableName(BaseModel):
    new_name: str = Field("The new variable name to use")
    reasoning: str = Field(
        "The reasoning behind choosing the new variable name"
    )


class UnderstandCode:
    def __init__(self, code, host=HOST, model=MODEL):
        self._base = code
        self._client = Client(host=host)
        self._llm = ChatOllama(
            base_url=host,
            model=model,
            format="json",
            temperature=0
        )
        self._summary = self.summerize()

    def summary_prompt(self):
        t = templateEnv.get_template('summary.txt')
        return HumanMessage(content=t.render(code=self._base))

    def new_name_prompt(self, name, variable_type):
        t = templateEnv.get_template('new_names.txt')
        return HumanMessage(
            t.render(variable_type=variable_type, variable_name=name)
        )

    def summerize(self):
        messages = [self.summary_prompt()]
        prompt = ChatPromptTemplate.from_messages(messages)
        chain = prompt | self._llm
        return chain.invoke({})

    def suggest_new_variable_name(self, name, variable_type):
        # note: we aren't using the format instructions because I found they
        # worked worse than my own prompt.
        parser = JsonOutputParser(pydantic_object=NewVariableName)

        nnp = self.new_name_prompt(name, variable_type)
        messages = [
            self.summary_prompt(),
            self._summary,
            nnp
        ]
        prompt = ChatPromptTemplate.from_messages(messages)

        chain = prompt | self._llm | parser

        return chain.invoke({})


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


@click.command()
@click.option('--filename', default='/dev/stdin')
@click.option('--model', default=MODEL)
@click.option('--host', default=HOST)
def main(filename, model, host):
    with open(filename, 'r') as f:
        base = f.read()

    t = templateEnv.get_template('wrapper.txt')
    data = t.render(code=process_radare2_symbols(base))

    # write to a tempfile
    func_info = {}
    with tempfile.NamedTemporaryFile() as fp:
        fp.write(bytes(data, encoding='utf-8'))
        fp.flush()
        func_info = get_func_info(fp.name)

    # Should only be one function defined
    uc = UnderstandCode(data, model=model, host=host)

    new_names = {}

    for func, definition in func_info.items():
        to_rename = {}
        seen_before = set()

        for arg, typedef in definition['arguments'].items():
            new = uc.suggest_new_variable_name(arg, ' '.join(typedef))
            new_name = normalize_name(new.get('new_name', arg))
            new_name = make_uniq(new_name, seen_before)
            seen_before.add(new_name)
            to_rename[arg] = new_name
            print(f'/* {arg} -> {new_name} */')

        for var, typedef in definition['variables'].items():
            new = uc.suggest_new_variable_name(var, ' '.join(typedef))
            new_name = normalize_name(new.get('new_name', var))
            new_name = make_uniq(new_name, seen_before)
            seen_before.add(new_name)
            to_rename[var] = new_name
            print(f'/* {var} -> {new_name} */')

        new_names[func] = to_rename

    # modify the AST to use the new names
    with tempfile.NamedTemporaryFile() as fp:
        fp.write(bytes(data, encoding='utf-8'))
        fp.flush()
        print(modify_variable_names(fp.name, new_names))


if __name__ == "__main__":
    main()
