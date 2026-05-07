import requests
import os
import time
import json
from tqdm import tqdm
import csv

# ================== 配置 ==================
SAVE_DIR = "anime_covers"
BATCH_SIZE = 50          # 每次请求数量
TOTAL = 3000
DELAY = 1.0              # 防限速（秒）
# ========================================

os.makedirs(SAVE_DIR, exist_ok=True)

def fetch_anime_page(page):
    query = """
    query ($page: Int, $perPage: Int) {
      Page(page: $page, perPage: $perPage) {
        media(sort: POPULARITY_DESC, type: ANIME) {
          id
          title { romaji english native }
          coverImage { large extraLarge }
        }
      }
    }
    """
    variables = {"page": page, "perPage": BATCH_SIZE}
    response = requests.post("https://graphql.anilist.co", json={"query": query, "variables": variables})
    if response.status_code != 200:
        print(f"请求失败: {response.status_code}")
        return []
    return response.json()["data"]["Page"]["media"]

def download_image(url, filepath):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return True
    except:
        pass
    return False

print("开始获取Top 3000动画封面...")

all_anime = []
csv_data = []

for page in tqdm(range(1, (TOTAL//BATCH_SIZE)+2), desc="获取列表"):
    media_list = fetch_anime_page(page)
    if not media_list:
        break
    all_anime.extend(media_list)
    time.sleep(DELAY)

print(f"共获取 {len(all_anime)} 部动画信息")

# 下载封面
success = 0
for anime in tqdm(all_anime[:TOTAL], desc="下载封面"):
    title = anime["title"]["romaji"] or anime["title"]["english"] or str(anime["id"])
    clean_title = "".join(c if c.isalnum() else "_" for c in title)[:100]
    url = anime["coverImage"]["extraLarge"] or anime["coverImage"]["large"]
    
    filepath = os.path.join(SAVE_DIR, f"{anime['id']}_{clean_title}.jpg")
    if download_image(url, filepath):
        success += 1
        csv_data.append([anime['id'], title, url, filepath])
    time.sleep(DELAY * 0.5)  # 下载也放慢点

# 保存索引
with open("anime_covers_index.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "title", "image_url", "local_path"])
    writer.writerows(csv_data)

print(f"\n✅ 完成！成功下载 {success} 张封面")
print(f"文件夹：{SAVE_DIR}")
print(f"索引文件：anime_covers_index.csv")