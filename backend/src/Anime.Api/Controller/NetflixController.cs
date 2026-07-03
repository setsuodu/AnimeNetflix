using Anime.Infrastructure.Context;
using Anime.Infrastructure.Entities;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Anime.Api.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class NetflixController : ControllerBase
    {
        private readonly AnimeDbContext _db;
        public NetflixController(AnimeDbContext db) => _db = db;

        [HttpGet]
        public async Task<IActionResult> GetList(int page = 1, int pageSize = 30, string? search = null)
        {
            var query = _db.Animes.AsNoTracking();

            if (!string.IsNullOrWhiteSpace(search))
                query = query.Where(x => x.Title.Contains(search));

            // 跟资源站一样：按更新时间倒序（最新更新的排最前面）
            var data = await query
                .OrderByDescending(x => x.SiteUpdateTime)     // ← 改这里
                .Skip((page - 1) * pageSize)
                .Take(pageSize)
                .ToListAsync();

            return Ok(data);
        }

        [HttpGet("{fingerprint}")]
        public async Task<IActionResult> GetDetail(string fingerprint)
        {
            Console.WriteLine($"GetDetail: {fingerprint}");

            var anime = await _db.Animes
                .AsNoTracking()
                .Select(x => new
                {
                    x.SourceFingerprint,   // 改为主键
                    x.Title,
                    x.CoverUrl,           // ← 加上这行
                    x.PlayUrls,
                    x.BackupUrls,
                    x.Episodes,
                    x.Year,
                    x.Area,
                    x.Category,
                    x.UpdateTime
                })
                .FirstOrDefaultAsync(x => x.SourceFingerprint == fingerprint);

            return anime == null ? NotFound() : Ok(anime);
        }

        // https://localhost:8060/api/netflix/maintenance/flush-jinying
        /// <summary>
        /// 【临时】修复：定义 PlayUrls = 金鹰，BackupUrls = 红牛，没有 m3u8 的补齐
        /// </summary>
        /// <returns></returns>
        [HttpGet("maintenance/flush-jinying")]
        public async Task<IActionResult> FlushJinYingData()
        {
            _db.Database.SetCommandTimeout(TimeSpan.FromSeconds(120));

            var animes = await _db.Animes
                .Where(a => a.PlayUrls.Contains("ijycnd.com"))
                .ToListAsync();

            int updatedCount = 0;

            foreach (var anime in animes)
            {
                bool isModified = false;
                var episodes = anime.PlayUrls.Split('#', StringSplitOptions.RemoveEmptyEntries);
                var fixedEpisodes = new List<string>();

                foreach (var ep in episodes)
                {
                    if (!ep.Contains("$"))
                    {
                        fixedEpisodes.Add(ep);
                        continue;
                    }

                    var parts = ep.Split('$');
                    var name = parts[0];
                    var url = parts[1].Trim();

                    if (url.Contains("ijycnd.com/play/") && !url.EndsWith(".m3u8"))
                    {
                        url = $"{url}/index.m3u8";
                        isModified = true;
                    }
                    fixedEpisodes.Add($"{name}${url}");
                }

                // 重点：如果原本是 null 或者你想清空它，用 "" 而不是 null[cite: 1]
                if (isModified || anime.BackupUrls != "")
                {
                    anime.PlayUrls = string.Join("#", fixedEpisodes);
                    anime.BackupUrls = ""; // 修复：使用空字符串满足 Postgres 的 NOT NULL 约束
                    isModified = true;
                }

                if (isModified) updatedCount++;
            }

            if (updatedCount > 0)
            {
                await _db.SaveChangesAsync();
            }

            return Ok(new
            {
                Message = "洗地完成",
                UpdatedRows = updatedCount,
                Status = "BackupUrls 已初始化为空字符串"
            });
        }

        // https://localhost:8060/api/netflix/export-for-manus
        /// <summary>
        /// 【临时】“全量导出”接口，找manus拉
        /// </summary>
        /// <returns></returns>
        [HttpGet("export-for-manus")]
        public async Task<IActionResult> ExportForManus()
        {
            var allData = await _db.Animes
                .AsNoTracking()
                .Select(x => new
                {
                    // 把 [第xx集]、[OVA]、[剧场版] 等全部去掉
                    Title = Regex.Replace(x.Title, @"\s*\[.*?\]", "").Trim(),
                    Title_JP = "", // 番剧日文原名
                    Title_EN = "", // 番剧英文名
                    CoverFile = "", // 封面文件名
                })
                .ToListAsync();

            return Ok(allData);
        }

        // https://localhost:8060/api/netflix/export-seed
        /// <summary>
        /// 【常驻】到出 SQL 成 json，迁移备份
        /// </summary>
        /// <remarks>
        /// 调用后会在项目目录生成 seed.json 文件，包含所有动漫信息。
        /// 新部署时 Program.cs 会自动读取这个文件进行 Seed 操作。
        /// </remarks>
        /// <returns>导出结果</returns>
        [HttpGet("export-seed")]
        public async Task<IActionResult> ExportSeedJson()
        {
            try
            {
                // 1. 拉取所有数据（包含你爬取的年份、地区、分类等全维度字段）
                var allData = await _db.Animes.AsNoTracking().ToListAsync();

                // 2. 序列化为 JSON，并保持格式整齐（方便 Git 对比变化）
                var options = new JsonSerializerOptions
                {
                    WriteIndented = true,
                    Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                };
                string jsonString = JsonSerializer.Serialize(allData, options);

                // 3. 写入项目根目录的 seed.json
                // 注意：在开发环境下，这会直接覆盖你项目文件夹里的文件
                string filePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "seed.json");

                // 为了确保能写回到源代码目录而非仅仅是输出目录，通常建议指定相对路径
                // 或者直接返回文件流让浏览器下载
                await System.IO.File.WriteAllTextAsync("seed.json", jsonString);

                return Ok(new
                {
                    Message = "seed.json 已更新",
                    Count = allData.Count,
                    Path = Path.GetFullPath("seed.json")
                });
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"导出失败: {ex.Message}");
            }
        }

        // https://localhost:8060/api/netflix/import-covers
        /// <summary>
        /// 【临时】manus 爬取的封面导入SQL
        /// </summary>
        /// <param name="imports"></param>
        /// <returns></returns>
        [HttpPost("import-covers")]
        public async Task<IActionResult> ImportCovers([FromBody] List<CoverImportDto> imports)
        {
            if (imports == null || imports.Count == 0)
                return BadRequest("数据为空");

            var updated = 0;
            foreach (var item in imports)
            {
                // 优先用 SourceFingerprint 精确匹配（最稳），其次模糊匹配 Title
                var anime = await _db.Animes
                    .FirstOrDefaultAsync(a =>
                        !string.IsNullOrEmpty(item.SourceFingerprint) && a.SourceFingerprint == item.SourceFingerprint ||
                        a.Title.Contains(item.Title) || a.Title == item.Title);

                if (anime != null && !string.IsNullOrWhiteSpace(item.CoverUrl))
                {
                    anime.CoverUrl = item.CoverUrl;   // 更新封面
                    if (!string.IsNullOrWhiteSpace(item.Title_JP))
                        anime.Title = item.Title_JP;  // 可选：更新日文名
                    if (!string.IsNullOrWhiteSpace(item.Title_EN))
                        anime.Title = item.Title_EN;  // 可选：更新英文名

                    updated++;
                }
            }

            await _db.SaveChangesAsync();

            return Ok(new { Message = $"✅ 成功更新 {updated} 条封面", UpdatedCount = updated });
        }

        // DTO（加在文件最下面）
        public class CoverImportDto
        {
            public string Title { get; set; } = string.Empty;
            public string Title_JP { get; set; } = string.Empty;
            public string Title_EN { get; set; } = string.Empty;
            public string CoverUrl { get; set; } = string.Empty;
            public string SourceFingerprint { get; set; } = string.Empty; // 可选
        }

        // https://localhost:8060/api/netflix/update-from-json
        /// <summary>
        /// 从 Manus_V2 的 JSON 补全 title_JP、title_EN、coverFile（只更新，不插入）
        /// </summary>
        [HttpPost("update-from-json")]
        public async Task<IActionResult> UpdateFromJson([FromBody] string? jsonPath = null)
        {
            jsonPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "anime_list_final_fixed.json");

            if (!System.IO.File.Exists(jsonPath))
            {
                return BadRequest($"JSON 文件不存在: {jsonPath}");
            }

            var json = await System.IO.File.ReadAllTextAsync(jsonPath);
            var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            var data = JsonSerializer.Deserialize<List<AnimeJsonItem>>(json, options);

            if (data == null || data.Count == 0)
                return BadRequest("JSON 数据为空");

            int updated = 0;
            foreach (var item in data)
            {
                var title = item.title?.Trim();
                if (string.IsNullOrEmpty(title)) continue;

                var jp = item.title_JP?.Trim() ?? "";
                var en = item.title_EN?.Trim() ?? "";
                var cover = item.coverFile?.Trim() ?? item.coverURL?.Trim() ?? "";

                var affected = await _db.Animes
                    .Where(a => a.Title == title)
                    .ExecuteUpdateAsync(sp => sp
                        .SetProperty(a => a.JapaneseTitle, a => string.IsNullOrEmpty(jp) ? a.JapaneseTitle : jp)
                        .SetProperty(a => a.EnglishTitle, a => string.IsNullOrEmpty(en) ? a.EnglishTitle : en)
                        .SetProperty(a => a.CoverUrl, a => string.IsNullOrEmpty(cover) ? a.CoverUrl : cover)
                        .SetProperty(a => a.UpdateTime, DateTime.UtcNow)
                    );

                if (affected > 0) updated++;
            }

            await _db.SaveChangesAsync();   // 确保

            Console.WriteLine($"✅ 从 JSON 更新完成，共更新 {updated} 条记录");
            return Ok(new { message = "更新完成", updatedCount = updated, totalProcessed = data.Count });
        }
    }

    // 辅助模型（只映射你需要的字段）
    public class AnimeJsonItem
    {
        public string? title { get; set; }
        public string? title_JP { get; set; }
        public string? title_EN { get; set; }
        public string? coverFile { get; set; }
        public string? coverURL { get; set; }
    }
}