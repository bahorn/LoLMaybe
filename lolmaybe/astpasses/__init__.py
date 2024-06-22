from pycparser import parse_file, c_ast, c_generator


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


class ASTProcess:
    """
    Perform passes over the C AST.
    """

    def __init__(self, filename):
        self._ast = parse_file(
            filename,
            use_cpp=True,
            cpp_args=r'-Iutils/fake_libc_include'
        )

    def run(self, user_pass):
        """
        Run a pass over the AST.
        """
        info, self._ast = user_pass.run(self._ast)
        return info

    def get_str(self):
        fp = FuncPrint()
        fp.visit(self._ast)
        return '\n\n'.join(fp.functions())
