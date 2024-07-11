import re
import requests
import getpass
import os

def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("bilibili_ssid")

# 环境变量
ssid = os.environ.get('bilibili_ssid')

# get请求的headers
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Host": "api.bilibili.com",
    "Cookie": f"SESSDATA={ssid}",
}


def fetch_subtitle(url: str):

    pattern = r"BV[\w]+"

    # Search for the pattern in the URL
    match = re.search(pattern, url)
    requested_url = "https://api.bilibili.com/x/web-interface/view?bvid="

    # Check if a match was found
    if match:
        bv_segment = match.group(0)[2:]
        requested_url += bv_segment
        print(f"Extracted segment: {bv_segment}")
    else:
        return "No matching segment found."
    
    response = requests.get(requested_url, headers=headers)

    if response.status_code == 200:
        print("initial url fetch success!")
    
    # 获取AID和CID
    response_json = response.json()
    aid = response_json['data']['aid']
    cid = response_json['data']['cid']

    # 第二次http请求获取存放subtitle地址的json
    subtitle_url = f'https://api.bilibili.com/x/player/v2?cid={cid}&aid={aid}'
    response_sub = requests.get(subtitle_url, headers=headers)

    # 转化成json用来提取信息
    response_sub_json = response_sub.json()
    subtitles = response_sub_json['data']['subtitle']['subtitles']

    if subtitles == None:
        print("Check SSID or this video does not have subtitles")
    
    print("the length of subtitles is: " + str(len(subtitles)))
    
    subtitle_all = ""
    for subtitle in subtitles:

        subtitle_url = "https:" + subtitle['subtitle_url']
        print(subtitle_url)

        subtitle_list = requests.get(subtitle_url)
        subtitle_list = subtitle_list.json()
        subtitle_list = subtitle_list['body']

        for subtitle in subtitle_list:
            subtitle_all += subtitle['content']

    return subtitle_all

