from functions import inference
from subtitle_process import fetch_subtitle
from templates import template_sub
import json
import re
import os
import getpass



def bv_to_url():
    #从页面所有BV号构建url
    urls = []
    with open('url.json', 'r') as file:
        urls = json.load(file)

    urls = ['https://'+item+'/' for item in urls]
    return urls

def get_subtitles(urls):
    #将前25个视频的字幕加入subtitles
    subtitles = []
    for url in urls[10:13]:
        sub = fetch_subtitle(url)
        subtitles.append(sub)

    return subtitles


def extract_question_explanations(responses):
    questions_and_explanations = []
    for response in responses:
        pattern = re.compile(r"### 原题：\n(.+?)\n\n### 讲解：\n(.+?)\n\n### 相似题一：\n(.+?)\n\n### 相似题一讲解：\n(.+?)\n\n### 相似题二：\n(.+?)\n\n### 相似题二讲解：\n(.+?)\n", re.DOTALL)
        matches = pattern.findall(response)

        for match in matches:
            questions_and_explanations.append({
                "original_question": match[0].strip(),
                "original_explanation": match[1].strip(),
                "similar_question_1": match[2].strip(),
                "similar_explanation_1": match[3].strip(),
                "similar_question_2": match[4].strip(),
                "similar_explanation_2": match[5].strip(),
            })

    with open('questions_explanation.json', 'w', encoding='utf-8') as f:
        json.dump(questions_and_explanations, f, ensure_ascii=False, indent=4)


async def run():
    os.environ['OPENAI_API_KEY'] = getpass.getpass()
    urls = bv_to_url()
    subtitles = get_subtitles(urls)
    responses = []
    for subtitle in subtitles:
        response = await inference({"subtitle": subtitle}, template_sub, 1000)
        responses.append(response)

    extract_question_explanations(responses)