import requests
import json
import time
import os
import re
from tqdm import tqdm
import unicodedata

# 配置
INPUT_FILE = "anime_list.json"
OUTPUT_FILE = "anime_list_final_fixed.json"
DOWNLOAD_DIR = "covers"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def sanitize_filename(name):
    """安全文件名"""
    name = unicodedata.normalize('NFKD', name)
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()[:200]
    return name

def clean_title(title):
    t = title.replace("《", "").replace("》", "")
    t = re.sub(r'(日语版|中文版|普通话版|原声版|（中配）|\(中配\)|第\d+季|第.+期| OVA| OAD| TV版| 剧场版|（国语版）)', '', t)
    t = t.split("（")[0].split("(")[0].strip()
    return t

def fetch_anilist(search_term):
    """优先用 trace.moe 代理（支持中文），失败再用官方"""
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
    proxies = [
        "https://trace.moe/anilist/",  # 带中文增强
        "https://graphql.anilist.co"
    ]
    
    for url in proxies:
        try:
            r = requests.post(url, 
                             json={"query": query, "variables": {"search": search_term}},
                             timeout=8,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                res = r.json().get("data", {}).get("Page", {}).get("media", [])
                if res:
                    m = res[0]
                    en = m['title']['english'] or m['title']['romaji'] or m['title']['native']
                    url_img = m['coverImage']['extraLarge'] or m['coverImage']['large']
                    return {"EN": en, "JP": m['title']['romaji'] or m['title']['native'], "URL": url_img}
        except:
            continue
    return None

def main():
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = []
    print(f"🚀 加强版启动！使用中文增强搜索，预计成功率大幅提升")

    for item in tqdm(data):
        orig_name = item.get("title") or item.get("Title")
        search_name = clean_title(orig_name)
        
        info = None
        candidates = [
            search_name,
            re.sub(r'第[一二三四五六七八九十]+季.*$', '', search_name).strip(),
            re.sub(r'[第 ]*[一二三四五六七八九十]+季', '', search_name).strip(),
        ]
        
        for term in candidates:
            if not term or len(term) < 2:
                continue
            info = fetch_anilist(term)
            if info:
                break
            time.sleep(0.6)  # 即使你说没限流，也稍微稳一点

        if info:
            try:
                img_data = requests.get(info["URL"], timeout=12,
                                      headers={"User-Agent": "Mozilla/5.0"}).content
                ext = info["URL"].split('.')[-1].split('?')[0].lower()
                ext = ext if ext in ['jpg', 'jpeg', 'png', 'webp'] else 'jpg'
                
                safe_name = sanitize_filename(info["EN"])
                filename = f"{safe_name}.{ext}"
                
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                
                item["title_EN"] = info["EN"]
                item["title_JP"] = info["JP"]
                item["coverFile"] = filename
                item["coverURL"] = info["URL"]
                item["status"] = "SUCCESS"
            except Exception as e:
                item["status"] = "IMG_ERR"
                print(f"图片下载失败: {orig_name} - {e}")
        else:
            item["status"] = "NOT_FOUND"
            print(f"未找到: {orig_name}")

        results.append(item)
        
        # 每10条存一次
        if len(results) % 10 == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("✅ 完成！")

if __name__ == "__main__":
    main()