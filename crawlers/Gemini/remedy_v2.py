import os
import json
import re
import time
import requests
from tqdm import tqdm

# ================== 核心配置 ==================
INPUT_FILE = "anime_list.json"
OUTPUT_FILE = "anime_list_final_fixed.json"
DOWNLOAD_DIR = "covers"  # 存放在脚本同级目录
TIMEOUT = 15

# 礼貌访问，带上 UA
HEADERS = {
    "User-Agent": "AnimeDataCleaner/1.0 (PC Testing; contact: local_dev)"
}

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def sanitize_filename(name):
    """移除 Windows 文件名非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '_', str(name))

def download_image(url, filename):
    """下载图片并重命名"""
    try:
        path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(path): return True
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
            return True
    except:
        pass
    return False

def get_from_wikipedia(title):
    """一级抓取：Wikipedia (定名核心)"""
    api_url = "https://zh.wikipedia.org/w/api.php"
    try:
        # 1. 搜索准确条目
        s_res = requests.get(api_url, params={
            "action": "query", "list": "search", "srsearch": title, "format": "json"
        }, headers=HEADERS, timeout=TIMEOUT).json()
        
        if not s_res['query']['search']: return None
        real_title = s_res['query']['search'][0]['title']
        
        # 2. 抓取语言链接和图片
        p_res = requests.get(api_url, params={
            "action": "query", "titles": real_title, "prop": "langlinks|pageimages",
            "lllimit": 50, "piprop": "original", "format": "json"
        }, headers=HEADERS, timeout=TIMEOUT).json()
        
        page = list(p_res['query']['pages'].values())[0]
        res = {"jp": "", "en": "", "img": page.get("original", {}).get("source", "")}
        
        for l in page.get('langlinks', []):
            if l['lang'] == 'ja': res['jp'] = l['*']
            if l['lang'] == 'en': res['en'] = l['*']
        return res
    except:
        return None

def get_from_bangumi(title):
    """二级抓取：Bangumi (补图核心)"""
    try:
        url = f"https://api.bgm.tv/search/subject/{requests.utils.quote(title)}"
        r = requests.get(url, params={"type": 2}, headers=HEADERS, timeout=TIMEOUT).json()
        if r.get('list'):
            item = r['list'][0]
            return {
                "jp": item.get('name'),
                "img": item.get('images', {}).get('large')
            }
    except:
        pass
    return None

def main():
    # 支持断点续传：优先读取已跑过的结果
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

    print(f"🚀 开始跑测试数据，共 {len(data)} 条...")

    for i in tqdm(range(len(data))):
        item = data[i]
        orig_title = item.get('title')
        
        # 只要字段还是空的，就跑一次逻辑
        if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile')):
            filename = f"{sanitize_filename(orig_title)}.jpg"
            
            # 1. 尝试 Wikipedia
            wiki = get_from_wikipedia(orig_title)
            if wiki:
                if not item.get('title_JP'): item['title_JP'] = wiki['jp']
                if not item.get('title_EN'): item['title_EN'] = wiki['en']
                if wiki['img'] and not item.get('coverFile'):
                    if download_image(wiki['img'], filename):
                        item['coverFile'] = f"covers/{filename}"

            # 2. 依然缺图或缺日文名？冲向 Bangumi
            if not item.get('title_JP') or not item.get('coverFile'):
                bgm = get_from_bangumi(orig_title)
                if bgm:
                    if not item.get('title_JP'): item['title_JP'] = bgm['jp']
                    if bgm['img'] and not item.get('coverFile'):
                        if download_image(bgm['img'], filename):
                            item['coverFile'] = f"covers/{filename}"

            # 最终数据清洗：如果英文名里被塞了中文，直接干掉
            if item.get('title_EN') and re.search(r'[\u4e00-\u9fa5]', item['title_EN']):
                item['title_EN'] = ""

            # 强制控制频率，维基百科不喜欢太快的
            time.sleep(0.8)

        # 每10条强制保存一次，防止断电
        if (i + 1) % 10 == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    # 最终保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✨ 测试任务完成！")

if __name__ == "__main__":
    main()