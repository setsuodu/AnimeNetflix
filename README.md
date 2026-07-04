# 自宅影院

## API 文档

https://github.com/setsuodu/AnimeNetflixDocs

## CI

当前项目的自动化有：
1. redoc文档：通过 push Anime.Api 触发;
2. animenetflix镜像：通过 tag 触发;

## 功能结构

1. 后端爬虫，定时爬金鹰
2. 数据库，保存m3u8
3. 前端影院，分集展示视频

```
AnimeNetflix/                        <-- 根目录 (docker-compose & Dockerfile 在这)
├── Dockerfile                       # 核心构建文件
├── docker-compose.yml               # PG 数据库 + API 容器
├── Anime.Api/                       # 主入口 (Web 服务)
│   ├── Controllers/                 # 提供 API 接口 (给前端调用)
│   ├── wwwroot/                     # 影院网站静态资源 (HTML/JS/CSS)
│   ├── Program.cs                   # 配置入口 (启用静态文件与跨域)
│   └── appsettings.json             # 数据库连接串
└── Anime.Infrastructure/            # 核心引擎 (对应你的 Shared + Playwright)
    ├── Context/                     # 数据库上下文 (AnimeDbContext)
    ├── Entities/                    # 数据库实体模型 (AnimeInfo)
    ├── Services/                    # 采集业务逻辑 (CrawlerService)
    ├── Migrations/                  # EF 数据库迁移脚本
    └── Anime.Infrastructure.csproj  # 这里引用 Playwright 和 EF 包
```

## 编译调试

1. Ctrl + ` 打开终端

D:\GitHub\[Workspace]\AnimeNetflix\

2. 确保停止并移除所有残留容器、网络
docker compose down

3. 手动删掉这个已经由于 Drop 导致损坏的数据目录

> 这一步是为了防止旧的锁文件阻止新容器启动
> [linux] 	rm -r -force ./postgres_data
> [windows] rd /s /q "postgres_data" 👈这个是docker-compose运行后生成的

4. 生成迁移：直接指向你的两个文件夹，别名都不用起
cd src
dotnet ef migrations add Init -p Anime.Infrastructure -s Anime.Api

5. 单拉起干净的数据库环境
docker compose up -d anime_db

6. 更新数据库（等等👆容器起来再执行）
dotnet ef database update -p Anime.Infrastructure -s Anime.Api

> 报红色的：Failed executing DbCommand ,,,, CommandTimeout='30' 是正常的

7. F5（调试） / docker compose up -d（拉起容器）

## 访问

8. https://localhost:8060/api/collector/run 👈开始爬取

### 默认模式（5个跳过自动结束）
```
POST https://localhost:8060/api/collector/run?id=24
```

### 全量抓取模式（不走跳过逻辑）
```
POST https://localhost:8060/api/collector/run?id=24&isFull=true
```
- 【爬虫完成】总耗时 1147.24 秒
- 【爬虫完成】总耗时 3032.81 秒

9. https://localhost:8060/api/netflix/export-seed 👈导出SQL种子

10. https://localhost:8060/ 👈影院首页

## 部署

1. 更新镜像

```
docker pull ghcr.io/setsuodu/animenetflix:latest
```

2. docker-compose

```
cd /vol1/1000/docker/animenetflix
docker compose up -d
```

## 数据迁移

方法一： Navicat 导出.sql
方法二： CI 自动构建，携带seed.json，启动就有

## TODO:

- [x] 1. docker-compose 第一次自动启动出错，应该是db未完全启动问题；
- [x] 2. 自动版本号，没写入；
- [x] 3. manus 爬取 cover，英文名，更新数据库；
- [x] 4. Episodes没写入；
- [x] 5. API整理；
- [x] 6. 目录整理；

## Android 调试

```
cd /d D:\Android\Sdk\platform-tools
adb logcat -c && adb logcat -v threadtime *:E *:W | findstr "AnimeAvalonia com.setsuodu"
```