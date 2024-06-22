import jinja2

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field

from defaults import HOST, MODEL

templateLoader = jinja2.FileSystemLoader(searchpath="./templates")
templateEnv = jinja2.Environment(loader=templateLoader)


class NewVariableName(BaseModel):
    new_name: str = Field("The new variable name to use")
    reasoning: str = Field(
        "The reasoning behind choosing the new variable name"
    )


class SummarizeCode:
    """
    Just get a brief summary of the code.
    """

    def __init__(self, code, host=HOST, model=MODEL):
        self._base = code
        self._llm = ChatOllama(
            base_url=host,
            model=model,
            temperature=0
        )

    def summary_prompt(self):
        t = templateEnv.get_template('summary.txt')
        return HumanMessage(content=t.render(code=self._base))

    def summerize(self):
        messages = [self.summary_prompt()]
        prompt = ChatPromptTemplate.from_messages(messages)
        chain = prompt | self._llm
        return messages + [chain.invoke({})]


class UnderstandCode:
    def __init__(self, code, host=HOST, model=MODEL):
        self._base = code
        self._llm = ChatOllama(
            base_url=host,
            model=model,
            format='json',
            temperature=0
        )
        sc = SummarizeCode(code, host, model)
        self._summary = sc.summerize()

    def new_name_prompt(self, name, variable_type):
        t = templateEnv.get_template('new_names.txt')
        return HumanMessage(
            t.render(variable_type=variable_type, variable_name=name)
        )

    def get_summary(self):
        return self._summary[1].content

    def suggest_new_variable_name(self, name, variable_type):
        # note: we aren't using the format instructions because I found they
        # worked worse than my own prompt.
        parser = JsonOutputParser(pydantic_object=NewVariableName)

        nnp = self.new_name_prompt(name, variable_type)
        messages = self._summary + [nnp]
        prompt = ChatPromptTemplate.from_messages(messages)

        chain = prompt | self._llm | parser

        return chain.invoke({})
