import time
import json
import re  # For regular expressions
import threading  # For multithreading
import requests  # To make HTTP requests
from openpyxl import Workbook  # To save data to an Excel file
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class GetInfo():
    def __init__(self, user_id):
        self.a_list = []  # 存储每一个视频的url
        self.d = webdriver.Chrome()  # 初始化Chrome浏览器驱动
        self.user_id = user_id
        self.base_url = f'https://space.bilibili.com/{user_id}/video'
        self.d.get(self.base_url)
        self.url_list = []
        #这篇文章写于2022年，当时B站免登入可以搜索视频，查看视频，但是这段时间再次尝试爬取资源时，加了必须认证登入，尝试过很多次，没有获取token，只能老老实实，登入后再去爬取信息
        time.sleep(10)
        print("速度扫码登入")

    def get_url(self):
        # 从当前页面获取所有视频的URL并保存到本地文件
        ul=WebDriverWait(self.d, 10).until(lambda x: x.find_element(By.XPATH, '//*[@id="submit-video-list"]/ul[1]'))
        lis = ul.find_elements(By.XPATH, "li")
        for li in lis:
            self.a_list.append(li.get_attribute("data-aid"))
        with open("url.json", "w+", encoding="utf-8") as f:
            data = json.dumps(self.a_list, ensure_ascii=False)  # 确保中文字符正常保存
            f.write(data)  # 使用write而不是writelines

    def next_page(self):
        # 遍历所有页面，获取所有视频的URL）
        total = WebDriverWait(self.d, 10).until(lambda x: x.find_element(By.XPATH, '//*[@id="submit-video-list"]/ul[3]/span[1]'))
        number = re.findall(r"\d+", total.text)
        total = int(number[0])
 
        for page in range(1, total):
            try:
                self.d.find_element(By.LINK_TEXT, '下一页').click()
                time.sleep(2)  # 等待页面加载
                self.get_url()  # 修复方法名错误
            except Exception as e:
                print(f"Failed to click next page: {e}")
 
        return self.a_list
    
    def get_video(self, urls, start, end):
        # 使用requests.Session()来复用TCP连接
        with requests.Session() as session:
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
            })
            base_url = "http://www.bilibili.com/video/"
 
            # 预编译正则表达式以提高性能
            title_pattern = re.compile(r'<title data-vue-meta="true">([^&amp;]+)</title>')
            play_count_pattern = re.compile(r'视频播放量 (\d+)')
            danmu_count_pattern = re.compile(r'弹幕量 (\d+)')
            like_count_pattern = re.compile(r'点赞数 (\d+)')
            coin_count_pattern = re.compile(r'投硬币枚数 (\d+)')
            favorite_count_pattern = re.compile(r'收藏人数 (\d+)')
            share_count_pattern = re.compile(r'转发人数 (\d+)')
 
            for url in urls[int(start):int(end)]:
                full_url = base_url + url
                try:
                    response = session.get(full_url)
                    if response.status_code == 200:
                        string = response.text
                        # 使用正则表达式提取视频信息
                        title_match = title_pattern.search(string)
                        title = title_match.group(1) if title_match else "未找到匹配的内容"
 
                        # 提取视频播放量、弹幕量等信息
                        play_count = play_count_pattern.search(string).group(1) if play_count_pattern.search(
                            string) else '0'
                        danmu_count = danmu_count_pattern.search(string).group(1) if danmu_count_pattern.search(
                            string) else '0'
                        like_count = like_count_pattern.search(string).group(1) if like_count_pattern.search(
                            string) else '0'
                        coin_count = coin_count_pattern.search(string).group(1) if coin_count_pattern.search(
                            string) else '0'
                        favorite_count = favorite_count_pattern.search(string).group(
                            1) if favorite_count_pattern.search(string) else '0'
                        share_count = share_count_pattern.search(string).group(1) if share_count_pattern.search(
                            string) else '0'
 
                        # 将提取的信息添加到self.data_list中
                        video_info = {
                            "url":full_url,
                            "title": title,
                            "play_count": play_count,
                            "danmu_count": danmu_count,
                            "like_count": like_count,
                            "coin_count": coin_count,
                            "favorite_count": favorite_count,
                            "share_count": share_count
                        }
                        self.data_list.append(video_info)
                    else:
                        print(f"Failed {full_url}: HTTP {response.status_code}")
                except Exception as e:
                    self.url_list.append(full_url)
                    print(f"Failed to get video info for url {full_url}: {e}")

    def save_to_excel(self, filename):
        wb = Workbook()
        ws = wb.active
        ws.append(['url','标题', '播放量', '弹幕数', '点赞数', '投币数', '收藏数', '分享数'])  # 添加表头
        for video_info in self.data_list:
            ws.append([
                video_info['url'],
                video_info['title'],
                video_info['play_count'],
                video_info['danmu_count'],
                video_info['like_count'],
                video_info['coin_count'],
                video_info['favorite_count'],
                video_info['share_count']
            ])
            wb.save(filename)

    def run(self):
         # 运行整个流程
        self.get_url()  # 获取当前页面的视频URL
        self.next_page()  # 遍历所有页面获取视频URL
 
        with open("url.json", "r", encoding="utf-8") as f:
            data = json.load(f)
 
            # 使用多线程提高数据获取效率
        threads = []
        part = int(len(data) / 3)
        for i in range(3):
            start = i * part
            end = (i + 1) * part if i != 2 else len(data)
            thread = threading.Thread(target=self.get_video, args=(data, start, end))
            threads.append(thread)
            thread.start()
 
        for thread in threads:
            thread.join()  # 等待所有线程完成
 
            # 所有线程完成后，保存数据到Excel
        self.save_to_excel('final_video_info1.xlsx')


if __name__ == '__main__':
    obj = GetInfo(523772889)
    obj.run()  # 运行整个流程