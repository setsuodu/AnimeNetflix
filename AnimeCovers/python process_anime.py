import requests
import json
import time
from tqdm import tqdm

# 配置
INPUT_FILE = pasted_file_P21g5Z_anime_list.json
OUTPUT_FILE = anime_list_updated.json
API_URL = httpsgraphql.anilist.co

def fetch_anime_info(search_term )
    从 AniList 获取动画信息
    query = 
    query ($search String) {
      Page(page 1, perPage 1) {
        media(search $search, type ANIME) {
          id
          title {
            native
          }
          coverImage {
            extraLarge
            large
          }
        }
      }
    }
    
    variables = {search search_term}
    try
        response = requests.post(API_URL, json={query query, variables variables}, timeout=10)
        if response.status_code == 200
            data = response.json()
            results = data.get(data, {}).get(Page, {}).get(media, [])
            if results
                anime = results[0]
                return {
                    title_JP anime['title']['native'],
                    coverFile anime['coverImage']['extraLarge'] or anime['coverImage']['large']
                }
    except Exception as e
        print(fn请求出错 [{search_term}] {e})
    return None

def main()
    try
        with open(INPUT_FILE, 'r', encoding='utf-8') as f
            anime_list = json.load(f)
    except FileNotFoundError
        print(f错误：找不到文件 {INPUT_FILE})
        return

    updated_list = []
    print(f开始处理 {len(anime_list)} 个动画项目...)
    
    # 为了演示效果，这里使用 tqdm 显示进度条
    for item in tqdm(anime_list, desc=匹配中)
        chinese_title = item.get(title, )
        if chinese_title
            # 清洗标题：去掉括号内容及常见后缀
            search_title = chinese_title.split(（)[0].split(()[0]
            search_title = search_title.replace(日语版, ).replace(中文版, ).replace(普通话版, ).strip()
            
            info = fetch_anime_info(search_title)
            if info
                item[title_JP] = info[title_JP]
                item[coverFile] = info[coverFile]
            else
                # 如果没搜到，保持原样
                item[title_JP] = item.get(title_JP, )
                item[coverFile] = item.get(coverFile, )
        
        updated_list.append(item)
        # 严格遵守 API 速率限制 (AniList 限制为 90 requestsminute)
        time.sleep(0.7) 
        
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f
        json.dump(updated_list, f, ensure_ascii=False, indent=2)
    
    print(fn✅ 处理完成！结果已保存至 {OUTPUT_FILE})

if __name__ == __main__
    main()
