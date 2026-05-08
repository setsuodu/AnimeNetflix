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

# 礼貌访问，带上 UA
HEADERS = {
    "User-Agent": "AnimeDataCleaner/1.0 (PC Testing; contact: local_dev)"
}

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# 用于多线程安全写入日志和文件的锁
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
    return re.sub(r'\\s+', ' ', name).strip()[:180]

def light_clean(title):
    t = str(title).strip()
    # 移除季数信息和括号内的版本信息，例如 (国语版)
    t = re.sub(r'(第[一二三四五六七八九十\\d]+季|（.+?版）|\\(.+?版\\))', '', t)
    return re.sub(r'\\s+', ' ', t).strip()

def pinyin_convert(text):
    """将中文文本转换为拼音，并用下划线连接"""
    if not text: return ""
    # 检查是否包含中文字符
    if not re.search(r'[\u4e00-\u9fa5]', text):
        return text # 不包含中文，直接返回
    
    # 将中文转换为拼音，每个字的首字母大写，用空格连接
    pinyin_list = pinyin(text, style=Style.FIRST_LETTER)
    # 过滤掉非字母字符，并连接成字符串
    pinyin_str = ''.join([item[0].upper() for item in pinyin_list if item[0].isalpha()])
    return pinyin_str

def short_clean(title):
    """尝试获取短标题，例如 '18if 梦境异闻录' -> '18if'"""
    # 匹配第一个空格、冒号、破折号、顿号、逗号、感叹号、问号等常见分隔符
    match = re.match(r'([^\\s:：—~～,，。！？!？]+)', title)
    if match:
        short_t = match.group(1).strip()
        if len(short_t) > 2: # 避免过短的标题，如 'A' 'B' 等
            return short_t
    return None

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
                headers=HEADERS,
                timeout=25
            )
            
            if r.status_code == 200:
                for item in r.json().get("data", []):
                    name = item.get("name", "")
                    name_cn = item.get("name_cn", "")
                    
                    # 收集所有可能的标题进行模糊匹配
                    all_titles = [name, name_cn] + item.get("infobox", {}).get("别名", [])
                    best_score = 0
                    best_match_title = ""

                    for t in all_titles:
                        if not t: continue
                        # 使用 SequenceMatcher 计算相似度
                        score = difflib.SequenceMatcher(None, search_term.lower(), t.lower()).ratio()
                        if score > best_score:
                            best_score = score
                            best_match_title = t
                    
                    # 设定一个阈值，例如 0.6，或者确保原始搜索词是某个标题的子串
                    if best_score >= 0.6 or search_term.lower() in (name.lower() + name_cn.lower()):
                        log(f"  ✓ Bangumi 命中: {name_cn or name} (原始搜索: {term}, 相似度: {best_score:.2f})", "DEBUG")
                        return {
                            "source": "Bangumi",
                            "EN": name_cn or name,
                            "JP": name,
                            "image": item.get("images", {}).get("large")
                        }
        except requests.exceptions.Timeout as e:
            log(f"  Bangumi 请求超时 ({term}): {e}", "TIMEOUT")
            return {"error": "TIMEOUT"}
        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code in [403, 429]:
                log(f"  Bangumi 频率限制 ({term}): {e.response.status_code}", "RATE_LIMITED")
                return {"error": "RATE_LIMITED"}
            log(f"  Bangumi 请求异常 ({term}): {e}", "API_ERROR")
            return {"error": "API_ERROR"}
        except json.JSONDecodeError as e:
            log(f"  Bangumi JSON 解析异常 ({term}): {e}", "JSON_ERROR")
            return {"error": "JSON_ERROR"}
        except Exception as e:
            log(f"  Bangumi 未知异常 ({term}): {e}", "ERROR")
            return {"error": "UNKNOWN_ERROR"}
    return None

def fetch_wikipedia(search_term):
    """Wikipedia opensearch 模糊搜索"""
    try:
        r = requests.get("https://zh.wikipedia.org/w/api.php", params={
            "action": "query",
            "list": "search",
            "format": "json",
            "srsearch": search_term,
            "srlimit": 5,
            "redirects": 1 # 自动跟随重定向
        }, timeout=20, headers=HEADERS)
        
        for res in r.json().get("query", {}).get("search", []):
            title = res.get("title", "")
            # 确保搜索词在标题中，避免无关结果
            if search_term.lower() in title.lower() or any(word.lower() in title.lower() for word in search_term.split()):
                # 获取页面详细信息，包括图片和语言链接
                # 获取页面详细信息，包括图片和语言链接
                page_info_r = requests.get("https://zh.wikipedia.org/w/api.php", params={
                    "action": "query", "format": "json", "titles": title,
                    "prop": "langlinks|pageimages|extracts", "lllimit": 50, "piprop": "original", "redirects": 1,
                    "explaintext": 1 # 返回纯文本内容
                }, timeout=15, headers=HEADERS)

                page_data = page_info_r.json().get("query", {}).get("pages", {})
                
                if not page_data: continue # 如果没有页面数据，跳过

                page = list(page_data.values())[0]
                real_title = page.get("title", title)
                jp_title = ""
                en_title = ""
                image_url = page.get("original", {}).get("source", "")

                # 尝试从页面内容中提取罗马字或官方英文译名
                extracted_en_title = ""
                extract = page.get("extract", "")
                # 常见的罗马字或英文名模式，例如括号内的英文
                match_roman = re.search(r'\(.*?([A-Za-z0-9\s\-:]+).*?\)', extract)
                if match_roman: extracted_en_title = match_roman.group(1).strip()

                for l in page.get("langlinks", []):
                    if l["lang"] == "ja": jp_title = l["*"]
                    if l["lang"] == "en": en_title = l["*"]
                
                # 优先使用从 extract 中提取的英文名
                if extracted_en_title: en_title = extracted_en_title
                
                if image_url or jp_title or en_title:
                    log(f"  ✓ Wikipedia 命中: {real_title} (原始搜索: {search_term})", "DEBUG")
                    return {
                        "source": "Wikipedia",
                        "EN": en_title or real_title,
                        "JP": jp_title or real_title,
                        "image": image_url
                    }
        except requests.exceptions.Timeout as e:
            log(f"  Wikipedia 请求超时 ({search_term}): {e}", "TIMEOUT")
            return {"error": "TIMEOUT"}
        except requests.exceptions.RequestException as e:
            if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code in [403, 429]:
                log(f"  Wikipedia 频率限制 ({search_term}): {e.response.status_code}", "RATE_LIMITED")
                return {"error": "RATE_LIMITED"}
            log(f"  Wikipedia 请求异常 ({search_term}): {e}", "API_ERROR")
            return {"error": "API_ERROR"}
        except json.JSONDecodeError as e:
            log(f"  Wikipedia JSON 解析异常 ({search_term}): {e}", "JSON_ERROR")
            return {"error": "JSON_ERROR"}
        except Exception as e:
            log(f"  Wikipedia 未知异常 ({search_term}): {e}", "ERROR")
            return {"error": "UNKNOWN_ERROR"}
    return None

def fetch_anilist(search_term):
    """AniList GraphQL API 抓取信息"""
    query = """query ($search: String) { Page(page: 1, perPage: 1) { media(search: $search, type: ANIME) { title { english romaji native } coverImage { extraLarge large } } } }"""
    try:
        r = requests.post("https://graphql.anilist.co", json={
            "query": query,
            "variables": {"search": search_term}
        }, timeout=20, headers=HEADERS)
        if r.status_code == 200:
            media = r.json().get("data", {}).get("Page", {}).get("media", [])
            if media:
                m = media[0]
                titles = m["title"]
                log(f"  ✓ AniList 命中: {titles.get('english') or titles.get('romaji')} (原始搜索: {search_term})", "DEBUG")
                return {
                    "source": "AniList",
                    "EN": titles.get("english") or titles.get("romaji"),
                    "JP": titles.get("native") or titles.get("romaji"),
                    "image": m["coverImage"].get("extraLarge") or m["coverImage"].get("large")
                }
    except requests.exceptions.Timeout as e:
        log(f"  AniList 请求超时 ({search_term}): {e}", "TIMEOUT")
        return {"error": "TIMEOUT"}
    except requests.exceptions.RequestException as e:
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code in [403, 429]:
            log(f"  AniList 频率限制 ({search_term}): {e.response.status_code}", "RATE_LIMITED")
            return {"error": "RATE_LIMITED"}
        log(f"  AniList 请求异常 ({search_term}): {e}", "API_ERROR")
        return {"error": "API_ERROR"}
    except json.JSONDecodeError as e:
        log(f"  AniList JSON 解析异常 ({search_term}): {e}", "JSON_ERROR")
        return {"error": "JSON_ERROR"}
    except Exception as e:
        log(f"  AniList 未知异常 ({search_term}): {e}", "ERROR")
        return {"error": "UNKNOWN_ERROR"}
    return None

def download_image(url, filename):
    """下载图片并重命名"""
    try:
        path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(path): 
            log(f"  图片已存在，跳过下载: {filename}", "DEBUG")
            return True
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
            log(f"  图片下载成功: {filename}", "DEBUG")
            return True
        else:
            log(f"  图片下载失败，状态码: {r.status_code} ({url})", "ERROR")
    except requests.exceptions.RequestException as e:
        log(f"  图片下载请求异常 ({url}): {e}", "ERROR")
    except Exception as e:
        log(f"  图片下载未知异常 ({url}): {e}", "ERROR")
    return False

# ====================== 处理单个 ==================
def process_item(item_index, all_data_list):
    """处理单个动漫条目，并更新共享数据列表"""
    item_data = all_data_list[item_index]
    orig_title = item_data.get("title", "")
    search_term_cleaned = light_clean(orig_title)

    log(f"开始处理 | {orig_title}", "PROCESS")
    if search_term_cleaned != orig_title:
        log(f"   清理后: {search_term_cleaned}", "CLEAN")

    info = None
    # 优先级：Bangumi -> Wikipedia -> AniList
    # 只有当当前条目缺少关键信息时才进行搜索
    if not (item_data.get('title_JP') and item_data.get('title_EN') and item_data.get('coverFile')):
        # 1. 尝试 Wikipedia (作为定名核心)
        info = fetch_wikipedia(search_term_cleaned)
        
        # 2. 如果 Wikipedia 没找到，或者只找到了标题但没有图片，尝试 Bangumi
        if not info or (not info.get('image') and (info.get('JP') or info.get('EN'))):
            bangumi_info = fetch_bangumi(search_term_cleaned)
            if bangumi_info:
                # 合并信息，Bangumi 优先提供图片和更准确的日文名
                if not info: info = bangumi_info
                else:
                    if not info.get('JP'): info['JP'] = bangumi_info.get('JP')
                    if not info.get('EN'): info['EN'] = bangumi_info.get('EN')
                    if not info.get('image'): info['image'] = bangumi_info.get('image')
                    info['source'] = f"{info['source']}+{bangumi_info['source']}"

        # 3. 如果 Bangumi 和 Wikipedia 都没能提供完整信息，尝试 AniList
        if not info or (not info.get('image') and (info.get('JP') or info.get('EN'))):
            anilist_info = fetch_anilist(search_term_cleaned)
            if anilist_info:
                # 合并信息，AniList 优先提供图片和英文名
                if not info: info = anilist_info
                else:
                    if not info.get('JP'): info['JP'] = anilist_info.get('JP')
                    if not info.get('EN'): info['EN'] = anilist_info.get('EN')
                    if not info.get('image'): info['image'] = anilist_info.get('image')
                    info['source'] = f"{info['source']}+{anilist_info['source']}"

        # 如果原始搜索未找到，尝试去季搜索
        if not info:
            no_season_title = re.sub(r'第[一二三四五六七八九十\d]+季.*$', '', search_term_cleaned).strip()
            if no_season_title and no_season_title != search_term_cleaned:
                log(f"   → 尝试去季搜索 (去季): {no_season_title}", "TRY")
                info = fetch_bangumi(no_season_title)
                if not info:
                    info = fetch_wikipedia(no_season_title)
                if not info:
                    info = fetch_anilist(no_season_title)

        # 如果去季搜索仍未找到，尝试短标题搜索 (例如 '18if 梦境异闻录' -> '18if')
        if not info:
            short_title = short_clean(search_term_cleaned)
            if short_title and short_title != search_term_cleaned:
                log(f"   → 尝试短标题搜索: {short_title}", "TRY")
                info = fetch_bangumi(short_title)
                if not info:
                    info = fetch_wikipedia(short_title)
                if not info:
                    info = fetch_anilist(short_title)

        # 如果短标题搜索仍未找到，尝试更激进的短标题清洗 (例如 '18if 梦境异闻录' -> '18if')
        if not info:
            # 进一步尝试从原始标题中提取更短的标题，例如只取第一个词
            aggressive_short_title = None
            if ' ' in orig_title:
                aggressive_short_title = orig_title.split(' ')[0].strip()
            elif '：' in orig_title:
                aggressive_short_title = orig_title.split('：')[0].strip()
            elif ':' in orig_title:
                aggressive_short_title = orig_title.split(':')[0].strip()
            
            if aggressive_short_title and aggressive_short_title != search_term_cleaned and aggressive_short_title != short_title and len(aggressive_short_title) > 2:
                log(f"   → 尝试更激进的短标题搜索: {aggressive_short_title}", "TRY")
                info = fetch_bangumi(aggressive_short_title)
                if not info:
                    info = fetch_wikipedia(aggressive_short_title)
                if not info:
                    info = fetch_anilist(aggressive_short_title)

    # 更新 item_data
    if info:
        if not item_data.get('title_JP') and info.get('JP'):
            item_data['title_JP'] = info['JP']
        if not item_data.get('title_EN') and info.get('EN'):
            item_data['title_EN'] = info['EN']
        
        # 如果有图片URL且当前没有封面文件，则尝试下            if info.get(\'image\') and not item_data.get(\'coverFile\'):
                # 确定封面文件名，确保纯 ASCII
                final_filename_base = ""
                # 优先级 1: 英文标题
                if item_data.get(\'title_EN\'):
                    temp_name = item_data[\'title_EN\']
                    # 检查是否纯ASCII
                    if all(ord(char) < 128 for char in temp_name):
                        final_filename_base = temp_name
                
                # 优先级 2: 原始中文标题转拼音 (如果英文标题不可用或非ASCII)
                if not final_filename_base and orig_title:
                    pinyin_name = pinyin_convert(orig_title)
                    if pinyin_name and all(ord(char) < 128 for char in pinyin_name):
                        final_filename_base = pinyin_name
                
                # 优先级 3: 如果以上都失败，使用原始标题（经过 sanitize_filename 处理）
                if not final_filename_base:
                    final_filename_base = orig_title

                filename = f"{sanitize_filename(final_filename_base)}.jpg"f download_image(info['image'], filename):
                item_data['coverFile'] = f"covers/{filename}"
                item_data['coverURL'] = info['image'] # 记录原始图片URL

    # 最终数据清洗：如果英文名里被塞了中文，仅移除中文
    if item_data.get('title_EN') and re.search(r'[\u4e00-\u9fa5]', item_data['title_EN']):
        item_data["title_EN"] = re.sub(r'[\u4e00-\u9fa5]', '', item_data["title_EN"]).strip()    # 强制控制频率，维基百科/AniList不喜欢太快的，Bangumi v0 API也需要控制
    time.sleep(0.8)

    # 使用锁确保文件写入安全，并实时保存
    with file_write_lock:
        # 直接更新原始列表中的元素
        all_data_list[item_index] = item_data 
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data_list, f, ensure_ascii=False, indent=2)
    
    if item_data.get('title_JP') or item_data.get('title_EN') or item_data.get('coverFile'):
        log(f"✅ 成功 | {orig_title} → {item_data.get('title_JP') or item_data.get('title_EN')} | 来源: {info.get('source') if info else 'N/A'}", "SUCCESS")
        return item_index, True
    else:
        log(f"⚠️ 未找到 | {orig_title} | 已尝试 Bangumi + Wikipedia + AniList", "NOT_FOUND")
        return item_index, False

# ====================== 主程序 ======================
def main():
    log("🚀 最终融合版启动 (Bangumi主 + Wiki辅助 + AniList补充 + 3并发 + 实时保存)", "START")
    
    # 支持断点续传：优先读取已跑过的结果
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {OUTPUT_FILE} 加载已处理数据，共 {len(data)} 条", "INFO")
    else:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {INPUT_FILE} 加载原始数据，共 {len(data)} 条", "INFO")

    # 使用 enumerate 获取索引，以便在多线程中更新原始列表
    # 过滤掉已经处理成功的条目，实现断点续传
    items_to_process_indices = [
        i for i, item in enumerate(data) 
        if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))
    ]
    
    log(f"待处理条目数: {len(items_to_process_indices)}", "INFO")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交任务，传递索引和整个数据列表
        futures = {executor.submit(process_item, i, data): i for i in items_to_process_indices}
        
        success_count = 0
        for future in tqdm(as_completed(futures), total=len(items_to_process_indices), desc="处理中"):
            try:
                item_idx, is_success = future.result()
                if is_success:
                    success_count += 1
            except Exception as exc:
                log(f'处理条目时发生异常: {exc}', "ERROR")

    # 最终保存一次，确保所有数据都已写入
    with file_write_lock:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"最终数据已保存到 {OUTPUT_FILE}", "INFO")

    # 生成失败列表
    failed_items = [item for item in data if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))]
    with open(FAILED_FILE, 'w', encoding='utf-8') as f:
        json.dump(failed_items, f, ensure_ascii=False, indent=2)
    log(f"失败条目已保存到 {FAILED_FILE}, 共 {len(failed_items)} 条", "INFO")

    total_processed = len(data) - len(items_to_process_indices) + success_count # 已经处理成功的 + 本次处理成功的
    log(f"🎉 完成！总条目 {len(data)}，本次成功处理 {success_count} 条，累计成功 {total_processed} 条，成功率 {total_processed/len(data)*100:.1f}%", "SUMMARY")

if __name__ == "__main__":
    main()ngumi v0 API也需要控制
    time.sleep(0.8)

    # 使用锁确保文件写入安全，并实时保存
    with file_write_lock:
        # 直接更新原始列表中的元素
        all_data_list[item_index] = item_data 
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data_list, f, ensure_ascii=False, indent=2)
    
    if item_data.get('title_JP') or item_data.get('title_EN') or item_data.get('coverFile'):
        log(f"✅ 成功 | {orig_title} → {item_data.get('title_JP') or item_data.get('title_EN')} | 来源: {info.get('source') if info else 'N/A'}", "SUCCESS")
        return item_index, True
    else:
        log(f"⚠️ 未找到 | {orig_title} | 已尝试 Bangumi + Wikipedia + AniList", "NOT_FOUND")
        return item_index, False

# ====================== 主程序 ======================
def main():
    log("🚀 最终融合版启动 (Bangumi主 + Wiki辅助 + AniList补充 + 3并发 + 实时保存)", "START")
    
    # 支持断点续传：优先读取已跑过的结果
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {OUTPUT_FILE} 加载已处理数据，共 {len(data)} 条", "INFO")
    else:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {INPUT_FILE} 加载原始数据，共 {len(data)} 条", "INFO")

    # 使用 enumerate 获取索引，以便在多线程中更新原始列表
    # 过滤掉已经处理成功的条目，实现断点续传
    items_to_process_indices = [
        i for i, item in enumerate(data) 
        if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))
    ]
    
    log(f"待处理条目数: {len(items_to_process_indices)}", "INFO")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交任务，传递索引和整个数据列表
        futures = {executor.submit(process_item, i, data): i for i in items_to_process_indices}
        
        success_count = 0
        for future in tqdm(as_completed(futures), total=len(items_to_process_indices), desc="处理中"):
            try:
                item_idx, is_success = future.result()
                if is_success:
                    success_count += 1
            except Exception as exc:
                log(f'处理条目时发生异常: {exc}', "ERROR")

    # 最终保存一次，确保所有数据都已写入
    with file_write_lock:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"最终数据已保存到 {OUTPUT_FILE}", "INFO")

    # 生成失败列表
    failed_items = [item for item in data if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))]
    with open(FAILED_FILE, 'w', encoding='utf-8') as f:
        json.dump(failed_items, f, ensure_ascii=False, indent=2)
    log(f"失败条目已保存到 {FAILED_FILE}, 共 {len(failed_items)} 条", "INFO")

    total_processed = len(data) - len(items_to_process_indices) + success_count # 已经处理成功的 + 本次处理成功的
    log(f"🎉 完成！总条目 {len(data)}，本次成功处理 {success_count} 条，累计成功 {total_processed} 条，成功率 {total_processed/len(data)*100:.1f}%", "SUMMARY")

if __name__ == "__main__":
    main()ime.sleep(0.8)

    # 使用锁确保文件写入安全，并实时保存
    with file_write_lock:
        # 直接更新原始列表中的元素
        all_data_list[item_index] = item_data 
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data_list, f, ensure_ascii=False, indent=2)
    
    if item_data.get('title_JP') or item_data.get('title_EN') or item_data.get('coverFile'):
        log(f"✅ 成功 | {orig_title} → {item_data.get('title_JP') or item_data.get('title_EN')} | 来源: {info.get('source') if info else 'N/A'}", "SUCCESS")
        return item_index, True
    else:
        log(f"⚠️ 未找到 | {orig_title} | 已尝试 Bangumi + Wikipedia + AniList", "NOT_FOUND")
        return item_index, False

# ====================== 主程序 ======================
def main():
    log("🚀 最终融合版启动 (Bangumi主 + Wiki辅助 + AniList补充 + 3并发 + 实时保存)", "START")
    
    # 支持断点续传：优先读取已跑过的结果
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {OUTPUT_FILE} 加载已处理数据，共 {len(data)} 条", "INFO")
    else:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {INPUT_FILE} 加载原始数据，共 {len(data)} 条", "INFO")

    # 使用 enumerate 获取索引，以便在多线程中更新原始列表
    # 过滤掉已经处理成功的条目，实现断点续传
    items_to_process_indices = [
        i for i, item in enumerate(data) 
        if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))
    ]
    
    log(f"待处理条目数: {len(items_to_process_indices)}", "INFO")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交任务，传递索引和整个数据列表
        futures = {executor.submit(process_item, i, data): i for i in items_to_process_indices}
        
        success_count = 0
        for future in tqdm(as_completed(futures), total=len(items_to_process_indices), desc="处理中"):
            try:
                item_idx, is_success = future.result()
                if is_success:
                    success_count += 1
            except Exception as exc:
                log(f'处理条目时发生异常: {exc}', "ERROR")

    # 最终保存一次，确保所有数据都已写入
    with file_write_lock:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"最终数据已保存到 {OUTPUT_FILE}", "INFO")

    # 生成失败列表
    failed_items = [item for item in data if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))]
    with open(FAILED_FILE, 'w', encoding='utf-8') as f:
        json.dump(failed_items, f, ensure_ascii=False, indent=2)
    log(f"失败条目已保存到 {FAILED_FILE}, 共 {len(failed_items)} 条", "INFO")

    total_processed = len(data) - len(items_to_process_indices) + success_count # 已经处理成功的 + 本次处理成功的
    log(f"🎉 完成！总条目 {len(data)}，本次成功处理 {success_count} 条，累计成功 {total_processed} 条，成功率 {total_processed/len(data)*100:.1f}%", "SUMMARY")

if __name__ == "__main__":
    main()item_data.get('title_EN')} | 来源: {info.get('source') if info else 'N/A'}", "SUCCESS")
        return item_index, True
    else:
        log(f"⚠️ 未找到 | {orig_title} | 已尝试 Bangumi + Wikipedia + AniList", "NOT_FOUND")
        return item_index, False

# ====================== 主程序 ======================
def main():
    log("🚀 最终融合版启动 (Bangumi主 + Wiki辅助 + AniList补充 + 3并发 + 实时保存)", "START")
    
    # 支持断点续传：优先读取已跑过的结果
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {OUTPUT_FILE} 加载已处理数据，共 {len(data)} 条", "INFO")
    else:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {INPUT_FILE} 加载原始数据，共 {len(data)} 条", "INFO")

    # 使用 enumerate 获取索引，以便在多线程中更新原始列表
    # 过滤掉已经处理成功的条目，实现断点续传
    items_to_process_indices = [
        i for i, item in enumerate(data) 
        if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))
    ]
    
    log(f"待处理条目数: {len(items_to_process_indices)}", "INFO")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交任务，传递索引和整个数据列表
        futures = {executor.submit(process_item, i, data): i for i in items_to_process_indices}
        
        success_count = 0
        for future in tqdm(as_completed(futures), total=len(items_to_process_indices), desc="处理中"):
            try:
                item_idx, is_success = future.result()
                if is_success:
                    success_count += 1
            except Exception as exc:
                log(f'处理条目时发生异常: {exc}', "ERROR")

    # 最终保存一次，确保所有数据都已写入
    with file_write_lock:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"最终数据已保存到 {OUTPUT_FILE}", "INFO")

    # 生成失败列表
    failed_items = [item for item in data if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))]
    with open(FAILED_FILE, 'w', encoding='utf-8') as f:
        json.dump(failed_items, f, ensure_ascii=False, indent=2)
    log(f"失败条目已保存到 {FAILED_FILE}, 共 {len(failed_items)} 条", "INFO")

    total_processed = len(data) - len(items_to_process_indices) + success_count # 已经处理成功的 + 本次处理成功的
    log(f"🎉 完成！总条目 {len(data)}，本次成功处理 {success_count} 条，累计成功 {total_processed} 条，成功率 {total_processed/len(data)*100:.1f}%", "SUMMARY")

if __name__ == "__main__":
    main()支持断点续传：优先读取已跑过的结果
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {OUTPUT_FILE} 加载已处理数据，共 {len(data)} 条", "INFO")
    else:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {INPUT_FILE} 加载原始数据，共 {len(data)} 条", "INFO")

    # 使用 enumerate 获取索引，以便在多线程中更新原始列表
    # 过滤掉已经处理成功的条目，实现断点续传
    items_to_process_indices = [
        i for i, item in enumerate(data) 
        if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))
    ]
    
    log(f"待处理条目数: {len(items_to_process_indices)}", "INFO")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交任务，传递索引和整个数据列表
        futures = {executor.submit(process_item, i, data): i for i in items_to_process_indices}
        
        success_count = 0
        for future in tqdm(as_completed(futures), total=len(items_to_process_indices), desc="处理中"):
            try:
                item_idx, is_success = future.result()
                if is_success:
                    success_count += 1
            except Exception as exc:
                log(f'处理条目时发生异常: {exc}', "ERROR")

    # 最终保存一次，确保所有数据都已写入
    with file_write_lock:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"最终数据已保存到 {OUTPUT_FILE}", "INFO")

    # 生成失败列表
    failed_items = [item for item in data if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))]
    with open(FAILED_FILE, 'w', encoding='utf-8') as f:
        json.dump(failed_items, f, ensure_ascii=False, indent=2)
    log(f"失败条目已保存到 {FAILED_FILE}, 共 {len(failed_items)} 条", "INFO")

    total_processed = len(data) - len(items_to_process_indices) + success_count # 已经处理成功的 + 本次处理成功的
    log(f"🎉 完成！总条目 {len(data)}，本次成功处理 {success_count} 条，累计成功 {total_processed} 条，成功率 {total_processed/len(data)*100:.1f}%", "SUMMARY")

if __name__ == "__main__":
    main()data.get('title_EN') or item_data.get('coverFile'):
        log(f"✅ 成功 | {orig_title} → {item_data.get('title_JP') or item_data.get('title_EN')} | 来源: {info.get('source') if info else 'N/A'}", "SUCCESS")
        return item_index, True
    else:
        log(f"⚠️ 未找到 | {orig_title} | 已尝试 Bangumi + Wikipedia + AniList", "NOT_FOUND")
        return item_index, False

# ====================== 主程序 ======================
def main():
    log("🚀 最终融合版启动 (Bangumi主 + Wiki辅助 + AniList补充 + 3并发 + 实时保存)", "START")
    
    # 支持断点续传：优先读取已跑过的结果
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {OUTPUT_FILE} 加载已处理数据，共 {len(data)} 条", "INFO")
    else:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        log(f"从 {INPUT_FILE} 加载原始数据，共 {len(data)} 条", "INFO")

    # 使用 enumerate 获取索引，以便在多线程中更新原始列表
    # 过滤掉已经处理成功的条目，实现断点续传
    items_to_process_indices = [
        i for i, item in enumerate(data) 
        if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))
    ]
    
    log(f"待处理条目数: {len(items_to_process_indices)}", "INFO")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交任务，传递索引和整个数据列表
        futures = {executor.submit(process_item, i, data): i for i in items_to_process_indices}
        
        success_count = 0
        for future in tqdm(as_completed(futures), total=len(items_to_process_indices), desc="处理中"):
            try:
                item_idx, is_success = future.result()
                if is_success:
                    success_count += 1
            except Exception as exc:
                log(f'处理条目时发生异常: {exc}', "ERROR")

    # 最终保存一次，确保所有数据都已写入
    with file_write_lock:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"最终数据已保存到 {OUTPUT_FILE}", "INFO")

    # 生成失败列表
    failed_items = [item for item in data if not (item.get('title_JP') and item.get('title_EN') and item.get('coverFile'))]
    with open(FAILED_FILE, 'w', encoding='utf-8') as f:
        json.dump(failed_items, f, ensure_ascii=False, indent=2)
    log(f"失败条目已保存到 {FAILED_FILE}, 共 {len(failed_items)} 条", "INFO")

    total_processed = len(data) - len(items_to_process_indices) + success_count # 已经处理成功的 + 本次处理成功的
    log(f"🎉 完成！总条目 {len(data)}，本次成功处理 {success_count} 条，累计成功 {total_processed} 条，成功率 {total_processed/len(data)*100:.1f}%", "SUMMARY")

if __name__ == "__main__":
    main()
