import json
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
import getpass
import os
import nest_asyncio
import asyncio
import re
from typing import Any, Dict, Tuple, List
from templates import extract_prompt
import torch
from langchain_openai import OpenAIEmbeddings
import torch
import base64
from langchain_core.messages import HumanMessage
from multiagent_func import run

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


async def get_similarity(p1: str, p2: str) -> float:
    # Constants for normalization
    MIN_OLD = 3
    MAX_OLD = 10
    MIN_NEW = 1
    MAX_NEW = 10
    WEIGHTS = [0.4, 0.2, 0.15, 0.05, 0.05, 0.15]
    NUM_MATCHES = len(WEIGHTS)  # Ensure we don't exceed available weights

    # Extract prompts for both problems
    att_p1 = await inference({"problem": p1}, extract_prompt)
    att_p2 = await inference({"problem": p2}, extract_prompt)

    # Extract matched questions from the prompts using regex
    pattern = r'\d+\.\s.*?:\s*(.*)'
    matches_p1 = re.findall(pattern, att_p1)
    matches_p2 = re.findall(pattern, att_p2)

    # Ensure we have enough matches to compare
    if len(matches_p1) < NUM_MATCHES or len(matches_p2) < NUM_MATCHES:
        raise ValueError(f"Not enough matches found in one of the problems. Expected {NUM_MATCHES} matches.")

    # Compute weighted cosine similarity
    total_similarity = sum(
        WEIGHTS[i] * cosimilarity(matches_p1[i], matches_p2[i])
        for i in range(NUM_MATCHES)
    )

    # Normalize the similarity score to the new range
    normalized_similarity = (
        ((total_similarity * 10 - MIN_OLD) / (MAX_OLD - MIN_OLD)) * (MAX_NEW - MIN_NEW) + MIN_NEW
    )

    return normalized_similarity



# Initialize a dictionary to cache text embeddings
text2embed = {}

def cosimilarity(p1: str, p2: str) -> torch.Tensor:
    # Initialize the embedding model
    embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")
    
    # Retrieve or compute the embedding for p1
    if p1 in text2embed: 
        p1_emb = text2embed[p1]
    else: 
        p1_emb = torch.tensor(embedding_model.embed_query(p1))
        text2embed[p1] = p1_emb
    
    # Retrieve or compute the embedding for p2
    if p2 in text2embed:
        p2_emb = text2embed[p2]
    else:
        p2_emb = torch.tensor(embedding_model.embed_query(p2))
        text2embed[p2] = p2_emb
    
    # Compute and return the cosine similarity
    cosine_similarity = torch.dot(p1_emb, p2_emb) / (torch.norm(p1_emb) * torch.norm(p2_emb))
    return cosine_similarity




async def search_similar(problem: str) -> List[int]:
    # Load the problem embeddings from the JSON file
    with open("problems_emb.json", 'r') as f:
        db_problem_emb = json.load(f)
    
    # Initialize the embedding model
    embedding_model = OpenAIEmbeddings(model='text-embedding-3-large')
    
    # Perform inference to extract the prompt
    temp = await inference({"problem": problem}, extract_prompt)
    
    # Extract queries from the prompt using regex
    pattern = r'\d+\.\s.*?:\s*(.*)'
    matches = re.findall(pattern, temp)
    
    # Embed each extracted query
    q_emb = [embedding_model.embed_query(match) for match in matches]
    q_emb = torch.tensor(q_emb)
    
    # Convert database embeddings to tensors
    problems_emb = torch.tensor(db_problem_emb)
    
    # Calculate similarity scores with specified weights
    weights = [0.4, 0.2, 0.15, 0.05, 0.05, 0.15]
    similar_scores = [
        sum(torch.dot(problems_emb[i][j], q_emb[j]) * weights[j] for j in range(len(weights)))
        for i in range(problems_emb.shape[0])
    ]
    
    # Sort and return the top 3 similar scores
    sorted_scores = sorted(range(len(similar_scores)), key=lambda x: similar_scores[x], reverse=True)
    return sorted_scores[:3]

async def image2sol(image_path: str) -> Tuple[str, str, str, dict]:
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    
    llm = ChatOpenAI(model='gpt-4o', max_tokens=1000)
    message = HumanMessage(
        content=[
            {"type": "text", "text": "请提取出图片中的题目，如果是选择题，请将选项也提取出来，不要输出题目以外的任何内容。如果图片中有解题需要的图形图片，请用语言对图片进行详细描述"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
            },
        ],
    )
    problem = llm.invoke([message])
    
    problem = problem.content
    sim_problems = await search_similar(problem)

    with open("problem_set_g7.json", 'r') as f:
        lookup_tab = json.load(f)
    for c in sim_problems:
        similar_prob = lookup_tab[c]
        print(similar_prob)

    note, explanation = run(problem, sim_problems, "七年级")
    return (note, explanation, sim_problems, problem)