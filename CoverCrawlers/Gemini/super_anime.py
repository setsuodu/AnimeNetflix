import requests
import json
import time
import os
import re
from tqdm import tqdm

# 配置
INPUT_FILE = "anime_list.json"
OUTPUT_FILE = "anime_list_final_fixed.json"
DOWNLOAD_DIR = "covers"

if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)

def clean_title(title):
    """把干扰词全部删掉，只留核心名"""
    t = title.replace("《", "").replace("》", "")
    t = re.sub(r'(日语版|中文版|普通话版|原声版|（中配）|\(中配\)|第\d+季|第.+期| OVA| OAD| TV版| 剧场版)', '', t)
    t = t.split("（")[0].split("(")[0].strip()
    return t

def fetch_direct(search_term):
    """直接硬磕 AniList"""
    query = """
    query ($search: String) {
      Page(page: 1, perPage: 1) {
        media(search: $search, type: ANIME) {
          title { english romaji native }
          coverImage { extraLarge large }
        }
      }
    }
    """
    try:
        r = requests.post("https://graphql.anilist.co", 
                         json={"query": query, "variables": {"search": search_term}}, 
                         timeout=5) # 缩短超时时间，不行就下一个
        if r.status_code == 200:
            res = r.json().get("data", {}).get("Page", {}).get("media", [])
            if res:
                m = res[0]
                return {
                    "EN": m['title']['english'] or m['title']['romaji'] or m['title']['native'],
                    "URL": m['coverImage']['extraLarge'] or m['coverImage']['large']
                }
    except: pass
    return None

def main():
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = []
    print(f"🚀 极速直联版启动！丢弃DDG，丢弃Wiki，只求速度和出图！")

    for item in tqdm(data):
        name = item.get("title") or item.get("Title")
        search_name = clean_title(name)
        
        # 直接拿 AniList 数据
        info = fetch_direct(search_name)
        
        if info:
            try:
                img_data = requests.get(info["URL"], timeout=10).content
                ext = info["URL"].split('.')[-1].split('?')[0]
                filename = "".join(x for x in info["EN"] if x.isalnum() or x in "._- ") + "." + (ext if len(ext)<=4 else "jpg")
                with open(os.path.join(DOWNLOAD_DIR, filename), 'wb') as f:
                    f.write(img_data)
                item["status"] = "SUCCESS"
            except:
                item["status"] = "IMG_ERR"
        else:
            item["status"] = "NOT_FOUND"
        
        # 即使失败也记录，每 5 个存一次盘防止 0kb
        results.append(item)
        if len(results) % 5 == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()