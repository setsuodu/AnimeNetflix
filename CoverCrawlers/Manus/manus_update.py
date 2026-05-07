import requests
import json
import time
import os
import re
from tqdm import tqdm

# 配置
INPUT_FILE = "anime_list.json"
OUTPUT_FILE = "anime_list_ultimate_log.json"
LOG_FILE = "debug_log.txt"
SAVE_DIR = "anime_covers"
ANILIST_API = "https://graphql.anilist.co"
BANGUMI_API = "https://api.bgm.tv/v0/search/subjects"
HEADERS = {"User-Agent": "ManusAgent/1.0 (TripleEngine-Log )"}

if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

def clean_title(title):
    t = re.sub(r'(日语版|中文版|普通话版|原声版|（中配）|\(中配\)|第\d+季|第.+期| OVA| OAD| TV版| 剧场版|动画版)', '', title)
    t = t.split("（")[0].split("(")[0].strip()
    return t

def get_jp_from_bangumi(keyword):
    """引擎 1: Bangumi 搜索"""
    try:
        payload = {"keyword": keyword, "filter": {"type": [2]}, "limit": 1}
        r = requests.post(BANGUMI_API, json=payload, headers=HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                log(f"Bangumi 匹配成功: {keyword} -> {data[0]['name']}")
                return data[0]['name']
    except Exception as e:
        log(f"Bangumi 异常: {e}")
    return None

def get_jp_from_wiki(keyword):
    """引擎 2: Wikipedia 联想搜索"""
    wiki_api = "https://zh.wikipedia.org/w/api.php"
    try:
        # 联想
        s_params = {"action": "opensearch", "search": keyword, "limit": 1, "format": "json"}
        s_resp = requests.get(wiki_api, params=s_params, timeout=5 ).json()
        if s_resp[1]:
            target = s_resp[1][0]
            # 找日文链接
            l_params = {"action": "query", "prop": "langlinks", "titles": target, "lllang": "ja", "format": "json", "redirects": 1}
            l_resp = requests.get(wiki_api, params=l_params, timeout=5).json()
            pages = l_resp.get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                if "langlinks" in pdata:
                    jp_name = pdata["langlinks"][0]["*"]
                    log(f"Wiki 转换成功: {keyword} -> {jp_name}")
                    return jp_name
    except Exception as e:
        log(f"Wiki 异常: {e}")
    return None

def fetch_anilist(search_term):
    """引擎 3: AniList 抓图"""
    query = """query ($search: String) { Page(page: 1, perPage: 1) { media(search: $search, type: ANIME) { id title { native } coverImage { extraLarge } } } }"""
    try:
        resp = requests.post(ANILIST_API, json={"query": query, "variables": {"search": search_term}}, timeout=5)
        if resp.status_code == 200:
            res = resp.json().get("data", {}).get("Page", {}).get("media", [])
            if res: return res[0]
    except: pass
    return None

def main():
    with open(LOG_FILE, "w", encoding="utf-8") as f: f.write("=== 三引擎深度调试日志 ===\n")
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f: anime_list = json.load(f)
    except: print(f"找不到文件 {INPUT_FILE}"); return

    updated_list = []
    print(f"🚀 三引擎启动！Bangumi + Wiki + AniList 联合围剿！")

    for item in tqdm(anime_list):
        title = item.get("title", "")
        log(f"--- 正在处理: {title} ---")
        clean_name = clean_title(title)
        
        # 1. 尝试 Bangumi
        jp_name = get_jp_from_bangumi(clean_name)
        
        # 2. 如果失败，尝试 Wikipedia
        if not jp_name:
            jp_name = get_jp_from_wiki(clean_name)
            
        # 3. 拿着结果去 AniList
        search_target = jp_name if jp_name else clean_name
        result = fetch_anilist(search_target)
        
        # 4. 最终尝试：直接用原名撞 AniList
        if not result and search_target != clean_name:
            result = fetch_anilist(clean_name)

        if result:
            item["title_JP"] = result['title']['native']
            img_url = result['coverImage']['extraLarge']
            # 下载逻辑
            try:
                img_path = os.path.join(SAVE_DIR, f"{result['id']}.jpg")
                if not os.path.exists(img_path):
                    with open(img_path, 'wb') as f: f.write(requests.get(img_url).content)
                item["coverFile"] = img_path
                log(f"✅ 成功获取封面: {item['title_JP']}")
            except: item["coverFile"] = img_url # 下不下来就存 URL
        else:
            log(f"❌ 彻底失败: {title}")
            item["title_JP"] = "NOT_FOUND"

        updated_list.append(item)
        if len(updated_list) % 5 == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(updated_list, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(updated_list, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 处理完成！请检查 {OUTPUT_FILE} 和 {LOG_FILE}")

if __name__ == "__main__":
    main()
