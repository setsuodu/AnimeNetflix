import requests
import json
import os
import re
from tqdm import tqdm
import unicodedata
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ================== 配置 ==================
INPUT_FILE = "anime_list.json"
OUTPUT_FILE = "anime_list_final_fixed.json"
DOWNLOAD_DIR = "covers"
LOG_FILE = "crawl_log.txt"
FAILED_FILE = "failed_to_manual_search.json"
MAX_WORKERS = 3

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

log_lock = threading.Lock()

def log(message, level="INFO"):
    with log_lock:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line)

def sanitize_filename(name):
    name = unicodedata.normalize('NFKD', str(name))
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return re.sub(r'\s+', ' ', name).strip()[:180]

# 因为你的JSON已清洗，这里只做轻度处理
def light_clean(title):
    t = str(title).strip()
    t = re.sub(r'(第[一二三四五六七八九十\d]+季|（.+?版）|\(.+?版\))', '', t)
    return re.sub(r'\s+', ' ', t).strip()

# ====================== API 函数 ======================
def fetch_bangumi(search_term):
    """超级加强版 Bangumi（解决 AYAKA 这类问题）"""
    candidates = [
        search_term,
        re.sub(r'[？?！!]', '', search_term).strip(),
        re.sub(r'\s*[-‐—～~]+\s*', ' ', search_term).strip(),   # 处理各种横线
        re.sub(r'\s+', '', search_term).strip(),               # 去空格
    ]
    
    for term in set(candidates):
        try:
            payload = {"keyword": term, "filter": {"type": [2]}, "limit": 5}
            r = requests.post(
                "https://api.bgm.tv/v0/search/subjects",
                json=payload,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=25
            )
            
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    name = item.get("name", "")
                    name_cn = item.get("name_cn", "")
                    
                    # 超级宽松匹配
                    term_lower = term.lower().replace(" ", "")
                    name_lower = name.lower().replace(" ", "")
                    name_cn_lower = name_cn.lower().replace(" ", "")
                    orig_lower = search_term.lower().replace(" ", "")
                    
                    if (term_lower in name_lower or term_lower in name_cn_lower or
                        orig_lower in name_lower or orig_lower in name_cn_lower or
                        "ayaka" in name_lower or "绫岛奇谭" in name_cn_lower):
                        
                        log(f"  ✓ Bangumi 命中: {name_cn or name} (原始搜索: {term})", "SUCCESS")
                        return {
                            "source": "Bangumi",
                            "EN": name_cn or name,
                            "JP": name,
                            "image": item.get("images", {}).get("large")
                        }
        except Exception as e:
            log(f"  Bangumi 异常: {e}", "ERROR")
    return None

def fetch_wikipedia(search_term):
    """Wikipedia opensearch 模糊搜索"""
    try:
        r = requests.get("https://zh.wikipedia.org/w/api.php", params={
            "action": "query",
            "list": "search",
            "format": "json",
            "srsearch": search_term,
            "srlimit": 5
        }, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        
        for res in r.json().get("query", {}).get("search", []):
            title = res.get("title", "")
            if search_term in title or any(word in title for word in search_term.split()):
                # 获取封面
                page_r = requests.get("https://zh.wikipedia.org/w/api.php", params={
                    "action": "query", "format": "json", "titles": title,
                    "prop": "pageimages", "piprop": "original"
                }, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                for page in page_r.json().get("query", {}).get("pages", {}).values():
                    if "original" in page.get("thumbnail", {}):
                        return {
                            "source": "Wikipedia",
                            "EN": title,
                            "JP": title,
                            "image": page["thumbnail"]["original"]["source"]
                        }
    except Exception as e:
        log(f"  Wikipedia 异常: {e}", "ERROR")
    return None

def fetch_anilist_for_image(search_term):
    """AniList 只用来抓图和补充英文"""
    query = """query ($search: String) { Page(page: 1, perPage: 1) { media(search: $search, type: ANIME) { title { english romaji native } coverImage { extraLarge large } } } }"""
    try:
        r = requests.post("https://graphql.anilist.co", json={
            "query": query,
            "variables": {"search": search_term}
        }, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            media = r.json().get("data", {}).get("Page", {}).get("media", [])
            if media:
                m = media[0]
                titles = m['title']
                return {
                    "EN": titles.get('english') or titles.get('romaji'),
                    "JP": titles.get('native') or titles.get('romaji'),
                    "image": m['coverImage'].get('extraLarge') or m['coverImage'].get('large')
                }
    except:
        pass
    return None

# ====================== 处理单个 ==================
def process_item(item):
    orig = item.get("title", "")
    search = light_clean(orig)

    log(f"开始处理 | {orig}", "PROCESS")
    if search != orig:
        log(f"   清理后: {search}", "CLEAN")

    # 优先级：Bangumi → Wikipedia → AniList（仅抓图）
    info = fetch_bangumi(search) or fetch_wikipedia(search)

    if not info:
        # 去季再试一次
        no_season = re.sub(r'第[一二三四五六七八九十\d]+季.*$', '', search).strip()
        if no_season != search:
            log(f"   → 去季搜索: {no_season}", "TRY")
            info = fetch_bangumi(no_season) or fetch_wikipedia(no_season)

    # AniList 只用来补充图片和英文
    if info and not info.get("image"):
        anilist_data = fetch_anilist_for_image(search)
        if anilist_data and anilist_data.get("image"):
            info["image"] = anilist_data["image"]
            if not info.get("EN"):
                info["EN"] = anilist_data["EN"]

    if info and info.get("image"):
        # 下载图片逻辑...
        try:
            url = info["image"]
            img_data = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"}).content
            ext = url.split('.')[-1].split('?')[0][:4].lower()
            ext = ext if ext in ['jpg','png','jpeg','webp'] else 'jpg'
            
            safe_name = sanitize_filename(info.get("EN") or info.get("JP") or orig)
            filename = f"{safe_name}.{ext}"
            
            with open(os.path.join(DOWNLOAD_DIR, filename), 'wb') as f:
                f.write(img_data)
            
            item["title_EN"] = info.get("EN", "")
            item["title_JP"] = info.get("JP", "")
            item["coverFile"] = filename
            item["coverURL"] = url
            item["status"] = "SUCCESS"
            log(f"✅ 成功 | {orig} → {info.get('JP') or info.get('EN')} | 来源: {info.get('source')}", "SUCCESS")
            return item, True
        except Exception as e:
            log(f"图片下载失败: {e}", "ERROR")

    log(f"⚠️ 未找到 | {orig}", "NOT_FOUND")
    item["status"] = "NOT_FOUND"
    return item, False

# ====================== 主程序 ======================
def main():
    log("🚀 最终融合版启动 (Bangumi主 + Wiki辅助 + 3并发)", "START")
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = []
    success = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_item = {executor.submit(process_item, item.copy()): item for item in data}
        
        for future in tqdm(as_completed(future_to_item), total=len(data), desc="处理中"):
            item, ok = future.result()
            results.append(item)
            if ok:
                success += 1

            # 每10条立即保存一次
            if len(results) % 10 == 0:
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)

    # 最终保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(FAILED_FILE, 'w', encoding='utf-8') as f:
        failed = [item for item in results if item.get("status") != "SUCCESS"]
        json.dump(failed, f, ensure_ascii=False, indent=2)

    log(f"🎉 完成！成功 {success}/{len(data)} 条 ≈ {success/len(data)*100:.1f}%", "SUMMARY")

if __name__ == "__main__":
    main()