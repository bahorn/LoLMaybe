from pycparser import c_ast


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


class ExtractVariables:
    def __init__(self):
        pass

    def run(self, ast):
        v = FuncDefVisitor()
        v.visit(ast)
        return (v.functions(), ast)
