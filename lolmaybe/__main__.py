import tempfile

import click
import jinja2
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field

import utils
from astpasses import ASTProcess
from astpasses.extract_variables import ExtractVariables
from astpasses.replace_variables import ReplaceVariableNames


MODEL = "deepseek-coder:6.7b"
HOST = 'http://localhost:11434'

templateLoader = jinja2.FileSystemLoader(searchpath="./templates")
templateEnv = jinja2.Environment(loader=templateLoader)


class NewVariableName(BaseModel):
    new_name: str = Field("The new variable name to use")
    reasoning: str = Field(
        "The reasoning behind choosing the new variable name"
    )


class UnderstandCode:
    def __init__(self, code, host=HOST, model=MODEL):
        self._base = code
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


@click.command()
@click.option('--filename', default='/dev/stdin')
@click.option('--model', default=MODEL)
@click.option('--host', default=HOST)
def main(filename, model, host):
    with open(filename, 'r') as f:
        base = f.read()

    t = templateEnv.get_template('wrapper.txt')
    data = t.render(code=utils.process_radare2_symbols(base))

    # write to a tempfile
    with tempfile.NamedTemporaryFile() as fp:
        fp.write(bytes(data, encoding='utf-8'))
        fp.flush()

        astp = ASTProcess(fp.name)

    func_info = astp.run(ExtractVariables())

    # Should only be one function defined
    uc = UnderstandCode(data, model=model, host=host)

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
