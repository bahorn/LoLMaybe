"""
Pipeline:
    * Summarize code
    * Think about task.
    * Do task.
"""

import jinja2

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, BaseMessage
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


class ChatModel:
    """
    Wrapper around chatting with the model, to do history management.
    """

    def __init__(self, host=HOST, model=MODEL):
        self._llm = ChatOllama(
            base_url=host,
            model=model,
            temperature=0
        )
        self._messages = []

    def add(self, message):
        if isinstance(message, list):
            self._messages += message
        else:
            self._messages.append(message)

    def chain(self, messages):
        prompt = ChatPromptTemplate.from_messages(messages)
        chain = prompt | self._llm
        return chain

    def ask(self, message, keep=True):
        query = self._messages + [message]
        chain = self.chain(query)
        resp = chain.invoke({})

        if keep:
            self._messages = query + [resp]

        return resp

    def reset(self):
        self._messages = []

    def get_messages(self):
        return self._messages


class ChatModelJSON(ChatModel):
    def __init__(self, py_object, host=HOST, model=MODEL):
        self._llm = ChatOllama(
            base_url=host,
            model=model,
            format='json',
            temperature=0
        )
        self._py_object = py_object
        self._messages = []

    def chain(self, messages):
        parser = JsonOutputParser(pydantic_object=self._py_object)
        return super().chain(messages) | parser


class LLMCodePass:
    """
    Base extracting information.
    """

    def name(self):
        return self.__name__

    def model_type(self):
        return ChatModel

    def history(self):
        """
        The name of the history to run the pass with.
        """

        return None

    def run(self, code, history):
        return (history, {})


class LLMCodeProcess:
    """
    Process the code using LLMs.
    """

    def __init__(self, code, host=HOST, model=MODEL):
        self._code = code
        self._host = host
        self._model = model
        self._history = {}

    def run(self, user_pass):
        history = user_pass.history()

        chat_history = user_pass.model_type()(
            host=self._host, model=self._model
        )

        pre = self._history.get(history)
        if pre:
            chat_history.add(pre)

        new_hist, resp = user_pass.run(self._code, chat_history)
        self._history[user_pass.name()] = new_hist.get_messages()

        if isinstance(resp, BaseMessage):
            return resp.content

        return resp


class SummaryPass(LLMCodePass):
    """
    Get a summary of the code.
    """

    def name(self):
        return 'summary'

    def summary_prompt(self, code):
        t = templateEnv.get_template('summary.txt')
        return HumanMessage(content=t.render(code=code))

    def run(self, code, history):
        return (history, history.ask(self.summary_prompt(code)))


class SuggestNewVariableNamePass(LLMCodePass):
    """
    Suggest a new name for a variable.
    """

    def __init__(self, variable, variable_type):
        self._name = variable
        self._variable_type = variable_type

    def name(self):
        return 'suggest_new'

    def history(self):
        return 'summary'

    def model_type(self):
        def new_model(host, model):
            return ChatModelJSON(NewVariableName, host, model)

        return new_model

    def new_name_prompt(self, name, variable_type):
        t = templateEnv.get_template('new_names.txt')
        return HumanMessage(
            t.render(
                variable_type=self._variable_type, variable_name=self._name
            )
        )

    def run(self, code, history):
        return (
            history,
            history.ask(self.new_name_prompt(None, None), keep=False)
        )
