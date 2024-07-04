from subtitle_process import fetch_subtitle
import json
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
import getpass
import os
import nest_asyncio
import asyncio
import re
from typing import Any, Dict


'''
输入一：一个包含template中所有变量以及对应值的字典
输入二：一个给gpt的prompt template
输入三：回答token数量限制, 默认1000
输出：gpt的回答
'''
async def inference(params: Dict[str, any], template: str, max_tokens=1000) -> str:
    output = ""
    llm = ChatOpenAI(
        model='gpt-4o',
        temperature=0,
        max_tokens=max_tokens,
        max_retries=2,
        timeout=20,
    )
    print("executing")

    prompt = PromptTemplate.from_template(template=template)
    parser = StrOutputParser()
    chain = prompt | llm | parser

    async for chunk in chain.astream(params, version="v2"):
        output += chunk
        print(chunk, end='', flush=True)

    return output