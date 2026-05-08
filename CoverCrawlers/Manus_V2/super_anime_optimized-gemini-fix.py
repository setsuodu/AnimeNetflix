import requests
import json
import os
import re
import time
from tqdm import tqdm
import unicodedata
import difflib
from bs4 import BeautifulSoup
from pypinyin import pinyin, Style
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ================== 配置 ==================
INPUT_FILE = "anime_list.json"
OUTPUT_FILE = "anime_list_final_fixed.json"
DOWNLOAD_DIR = "covers"
LOG_FILE = "crawl_log.txt"
FAILED_FILE = "failed_to_manual_search.json"
MAX_WORKERS = 3 # 并发线程数

HEADERS = {
    "User-Agent": "AnimeDataCleaner/1.0 (PC Testing; contact: local_dev)"
}

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

log_lock = Lock()
file_write_lock = Lock()

def log(message, level="INFO"):
    with log_lock:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line)

def sanitize_filename(name):
    name = unicodedata.normalize("NFKD", str(name))
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return re.sub(r'\s+', ' ', name).strip()[:180]

def light_clean(title):
    t = str(title).strip()
    t = re.sub(r'(第[一二三四五六七八九十\d]+季|（.+?版）|\(.+?版\))', '', t)
    return re.sub(r'\s+', ' ', t).strip()

def pinyin_convert(text):
    if not text: return ""
    if not re.search(r'[\u4e00-\u9fa5]', text):
        return text
    pinyin_list = pinyin(text, style=Style.FIRST_LETTER)
    pinyin_str = ''.join([item[0].upper() for item in pinyin_list if item[0].isalpha()])
    return pinyin_str

def short_clean(title):
    match = re.match(r'([^\\s:：—~～,，。！？!？]+)', title)
    if match:
        short_t = match.group(1).strip()
        if len(short_t) > 2:
            return short_t
    return None

# ====================== API 函数 ======================
def fetch_bangumi(search_term):
    candidates = [
        search_term,
        re.sub(r'[？?！!]', '', search_term).strip(),
        re.sub(r'\s*[-‐—～~]+\s*', ' ', search_term).strip(),
        re.sub(r'\s+', '', search_term).strip(),
    ]
    
    for term in set(candidates):
        try:
            payload = {"keyword": term, "filter": {"type": [2]}, "limit": 5}
            r = requests.post("https://api.bgm.tv/v0/search/subjects", json=payload, headers=HEADERS, timeout=25)
            
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    name = item.get("name", "")
                    name_cn = item.get("name_cn", "")
                    all_titles = [name, name_cn] + (item.get("infobox", {}).get("别名", []) if isinstance(item.get("infobox"), dict) else [])
                    
                    best_score = 0
                    for t in all_titles:
                        if not t: continue
                        score = difflib.SequenceMatcher(None, search_term.lower(), t.lower()).ratio()
                        if score > best_score: best_score = score
                    
                    if best_score >= 0.6 or search_term.lower() in (name.lower() + name_cn.lower()):
                        return {"source": "Bangumi", "EN": name_cn or name, "JP": name, "image": item.get("images", {}).get("large")}
        except Exception as e:
            log(f"Bangumi 异常 ({term}): {e}", "ERROR")
    return None

def fetch_wikipedia(search_term):
    try:
        r = requests.get("https://zh.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "format": "json", "srsearch": search_term, "srlimit": 5, "redirects": 1
        }, timeout=20, headers=HEADERS)
        
        for res in r.json().get("query", {}).get("search", []):
            title = res.get("title", "")
            # 修改：增加 rvprop=content 以抓取 Infobox 源码
            page_info_r = requests.get("https://zh.wikipedia.org/w/api.php", params={
                "action": "query", "format": "json", "titles": title,
                "prop": "langlinks|pageimages|extracts|revisions", "rvprop": "content", 
                "lllimit": 50, "piprop": "original", "redirects": 1, "explaintext": 1
            }, timeout=15, headers=HEADERS)

            page_data = page_info_r.json().get("query", {}).get("pages", {})
            if not page_data: continue
            page = list(page_data.values())[0]
            
            jp_title, en_title = "", ""
            # 尝试从语言链接找英文名
            for l in page.get("langlinks", []):
                if l["lang"] == "ja": jp_title = l["*"]
                if l["lang"] == "en": en_title = l["*"]
            
            # --- 核心迭代：解析 Infobox 里的罗马音/英文名 ---
            if "revisions" in page:
                wikitext = page["revisions"][0]["*"]
                # 匹配罗马字或英文名称字段
                romaji_match = re.search(r'\|\s*(?:罗马字|罗马字|romaji)\s*=\s*(.*?)\s*[\|\}\n]', wikitext)
                if romaji_match:
                    en_title = romaji_match.group(1).strip()
                elif not en_title:
                    eng_name_match = re.search(r'\|\s*(?:英文名称|english_title)\s*=\s*(.*?)\s*[\|\}\n]', wikitext)
                    if eng_name_match:
                        en_title = eng_name_match.group(1).strip()

            return {
                "source": "Wikipedia",
                "EN": en_title or title,
                "JP": jp_title or title,
                "image": page.get("original", {}).get("source", "")
            }
    except Exception as e:
        log(f"Wikipedia 异常 ({search_term}): {e}", "ERROR")
    return None

def fetch_anilist(search_term):
    query = """query ($search: String) { Page(page: 1, perPage: 1) { media(search: $search, type: ANIME) { title { english romaji native } coverImage { extraLarge large } } } }"""
    try:
        r = requests.post("https://graphql.anilist.co", json={"query": query, "variables": {"search": search_term}}, timeout=20, headers=HEADERS)
        if r.status_code == 200:
            media = r.json().get("data", {}).get("Page", {}).get("media", [])
            if media:
                m = media[0]
                return {
                    "source": "AniList",
                    "EN": m["title"].get("english") or m["title"].get("romaji"),
                    "JP": m["title"].get("native") or m["title"].get("romaji"),
                    "image": m["coverImage"].get("extraLarge") or m["coverImage"].get("large")
                }
    except Exception as e:
        log(f"AniList 异常 ({search_term}): {e}", "ERROR")
    return None

def download_image(url, filename):
    try:
        path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(path): return True
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
            return True
    except Exception as e:
        log(f"图片下载异常: {e}", "ERROR")
    return False

# ====================== 处理单个 ==================
def process_item(item_index, all_data_list):
    item_data = all_data_list[item_index]
    orig_title = item_data.get("title", "")
    search_term = light_clean(orig_title)

    log(f"开始处理 | {orig_title}", "PROCESS")
    info = None

    # 尝试不同来源 (保持原有顺序)
    for func in [fetch_wikipedia, fetch_bangumi, fetch_anilist]:
        info = func(search_term)
        if info and info.get('image'): break

    # 更新数据
    if info:
        item_data['title_JP'] = info.get('JP')
        item_data['title_EN'] = info.get('EN')
        
        # --- 核心迭代：判断保存图片的名字是否是英文，不是则强转拼音 ---
        en_candidate = info.get('EN', '')
        # 如果检测到中文字符，哪怕是 API 返回的 EN 字段，也要强转拼音作为文件名
        if re.search(r'[\u4e00-\u9fa5]', en_candidate):
            file_base = pinyin_convert(orig_title)
        else:
            file_base = en_candidate or pinyin_convert(orig_title) or "anime_cover"
        
        filename = f"{sanitize_filename(file_base)}.jpg"
        
        if info.get('image') and download_image(info['image'], filename):
            item_data['coverFile'] = f"covers/{filename}"
            item_data['coverURL'] = info['image']

    # 强制清理英文名中的中文 (保持原有清理逻辑)
    if item_data.get('title_EN'):
        item_data["title_EN"] = re.sub(r'[\u4e00-\u9fa5]', '', item_data["title_EN"]).strip()

    time.sleep(0.8)

    with file_write_lock:
        all_data_list[item_index] = item_data 
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data_list, f, ensure_ascii=False, indent=2)
    
    return item_index, bool(info)

# ====================== 主程序 (仅修改进度条和日志标记) ======================
def main():
    log("🚀 启动 (Wiki + Bangumi + AniList)", "START")
    
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

    # 1. 筛选待处理索引
    indices_to_process = [i for i, item in enumerate(data) if not item.get('coverFile')]
    total = len(indices_to_process)
    
    log(f"📊 任务队列就绪，共计 {total} 个条目待抓取", "INFO")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_item, i, data): i for i in indices_to_process}
        
        # 2. 改进进度显示
        completed_count = 0
        for future in tqdm(as_completed(futures), total=total, desc="爬取进度"):
            completed_count += 1
            idx, success = future.result()
            title = data[idx].get('title', 'Unknown')
            
            # 3. 改进日志标记：用 ✅/❌ 且带上 [当前/总数]
            if success:
                log(f"✅ [{completed_count}/{total}] 索引 {idx} 处理成功: {title}", "PROGRESS")
            else:
                log(f"❌ [{completed_count}/{total}] 索引 {idx} 处理失败: {title}", "PROGRESS")

    log("🎉 所有条目处理完毕！", "SUMMARY")