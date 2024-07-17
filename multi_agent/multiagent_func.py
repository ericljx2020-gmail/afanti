from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, StateGraph, START
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_experimental.tools import PythonREPLTool

from typing import Annotated, Sequence, TypedDict
import functools
import operator

from new_templates import *

# HyperParams
# grade_value = "三年级"
log = []

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str

python_repl_tool = PythonREPLTool()

members = ["Noter", "Explainer", "Validator"]

system_prompt = (
    "你是一名监督员，负责管理以下成员之间的对话：{members}。"
    "根据以下用户请求，指定下一个需要行动的成员。每个成员将执行一个任务,"
    "你的任务是安排Noter, Explainer, Validator之间的工作，让他们合作写出一个完美的题目解析"
    "如果Validator认为Noter的板书超纲或者有修改建议给Noter，应该将修改建议返回给Noter让其根据修改建议重新生成符合要求的解题板书"
    "当Noter重新生成板书后，请将Noter的板书再次传递给Validator查验，只有当Validator的评价良好，且不再给出修改建议的时候，转去Explainer"
    "老师的讲解风格以及讲题思路，生成题目解析"
    "每一步反馈他们的结果和状态。任务完成后，请回复“FINISH”。"
)

options = ["FINISH"] + members

function_def = {
    "name": "route",
    "description": "选择下一个执行的成员",
    "parameters": {
        "title": "routeSchema",
        "type": "object",
        "properties": {
            "next": {
                "title": "Next",
                "anyOf": [
                    {"enum": options},
                ],
            }
        },
        "required": ["next"],
    }
}

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            "根据以上内容，下一步应该轮到谁了？"
            "或者我们是否已经得到不错的讲解，可以“完成”了呢？"
            "请从以下选项中选一个：{options}",
        ),
    ]
).partial(options=str(options), members=', '.join(members))

llm = ChatOpenAI(model="gpt-4o", max_tokens=1000)

supervisor_chain = (
    prompt
    | llm.bind_functions(functions=[function_def], function_call="route")
    | JsonOutputFunctionsParser()
)

'''
用来创建agent的帮助函数
'''
def create_agent(llm: ChatOpenAI, tools: list, system_prompt: str):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                'system',
                system_prompt
            ),
            MessagesPlaceholder(variable_name='messages'),
            MessagesPlaceholder(variable_name='agent_scratchpad')
        ]
    )
    agent = create_openai_tools_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools)
    return executor

'''
用来创建langgraph中为agent的node
'''
def agent_node(state, agent, name, log):
    result = agent.invoke(state)
    log[name] = result['output']
    return {"messages": [HumanMessage(content=result['output'], name=name)]}

def supervisor_node(state, log):
    result = supervisor_chain.invoke(state)
    log['Supervisor'] = result
    return result

def run(orig_problem, similar_problem, similar_solution, grade_value) -> list:
    global validator_template
    log = {}
    record = [] 
    noter_agent = create_agent(llm, [python_repl_tool], noter_template)
    noter_node = functools.partial(agent_node, agent=noter_agent, name='Noter', log=log)

    explainer_agent = create_agent(llm, [python_repl_tool], explainer_template)
    explainer_node = functools.partial(agent_node, agent=explainer_agent, name='Explainer', log=log)

    validator_template = validator_template.format(grade=grade_value)

    validator_agent = create_agent(llm, [python_repl_tool], validator_template)
    validator_node = functools.partial(agent_node, agent=validator_agent, name='Validator', log=log)

    workflow = StateGraph(AgentState)
    workflow.add_node("Noter", noter_node)
    workflow.add_node("Explainer", explainer_node)
    workflow.add_node("Validator", validator_node)
    workflow.add_node("Supervisor", functools.partial(supervisor_node, log=log))

    for member in members:
        workflow.add_edge(member, 'Supervisor')

    conditional_map = {k:k for k in members}
    conditional_map['FINISH'] = END
    # 根据Supervisor返回的Next值，选择对应conditional_map里面的agent
    workflow.add_conditional_edges("Supervisor", lambda x: x["next"], conditional_map)
    workflow.add_edge(START, 'Supervisor')

    graph = workflow.compile()

    try:
        for s in graph.stream(
            {
                "messages": [
                    HumanMessage(content=similar_problem),
                    HumanMessage(content=similar_solution),
                    HumanMessage(content=orig_problem),
                ]
            },
            {"recursion_limit": 12},
        ):
            if "__end__" not in s:
                record.append(s)
                print(s)
                print("----")
    except RecursionError as e:
        print(f"题目可能无法用{grade_value}的知识点解出，请检查题目是否包含超纲内容。")
        return [f"题目可能无法用{grade_value}的知识点解出，请检查题目是否包含超纲内容。",f"题目可能无法用{grade_value}的知识点解出，请检查题目是否包含超纲内容。"]
    noter_log = []
    explainer_log = []
    for item in record:
        for role in item:
            if role == "Supervisor" or role == "Validator": continue
            if role == "Noter":
                noter_log.append(item[role]['messages'][0].content)
            if role == "Explainer":
                explainer_log.append(item[role]['messages'][0].content)
    return [noter_log[-1], explainer_log[-1]]