from pycparser import c_ast


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


class ReplaceVariableNames:
    def __init__(self, new_names):
        self._new_names = new_names

    def run(self, ast):
        """
        Modify the AST to change the variable names and return the modified
        code.
        """
        v = FuncReplacerVisitor(self._new_names)
        v.visit(ast)
        return (None, ast)
