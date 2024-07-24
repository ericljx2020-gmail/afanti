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
from templates import extract_prompt
import torch
from langchain_openai import OpenAIEmbeddings


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


#function 输入两题，返回两题的cos similarity
async def get_similarity(p1: str, p2: str) -> float:
    tot = 0
    min_old = 3
    max_old = 10
    min_new = 1
    max_new = 10
    weights = [0.4, 0.2, 0.15, 0.05, 0.05, 0.15]
    extc_p1 = []
    extc_p2 = []
    att_p1 = await inference({"problem": p1}, extract_prompt)
    att_p2 = await inference({"problem": p2}, extract_prompt)
    pattern = r'\d+\.\s.*?:\s*(.*)'
    matches_p1 = re.findall(pattern, att_p1)
    matches_p2 = re.findall(pattern, att_p2)
    for i, match in enumerate(matches_p1, 1):
        extc_p1.append(match)
    for i, match in enumerate(matches_p2, 1):
        extc_p2.append(match)
    for i in range(6):
        tot += weights[i] * cosimilarity(extc_p1[i], extc_p2[i])
    return ((tot * 10 - min_old) / (max_old - min_old)) * (max_new - min_new) + min_new


text2embed = {}
def cosimilarity(p1: str, p2: str):
    embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")
    if p1 in text2embed: 
        p1_emb = text2embed.get(p1)
    else: 
        p1_emb = torch.tensor(embedding_model.embed_query(p1))
        text2embed[p1] = p1_emb
    if p2 in text2embed:
        p2_emb = text2embed.get(p2)
    else:
        p2_emb = torch.tensor(embedding_model.embed_query(p2))
        text2embed[p2] = p2_emb
    return torch.dot(p1_emb, p2_emb) / (torch.norm(p1_emb) * torch.norm(p2_emb))