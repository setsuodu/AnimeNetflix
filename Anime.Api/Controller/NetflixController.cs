using Anime.Infrastructure.Context;
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

            // 分页逻辑：Skip 跳过前面的，Take 拿现在的[cite: 7]
            var data = await query
                .OrderByDescending(x => x.Id)
                .Skip((page - 1) * pageSize)
                .Take(pageSize)
                .ToListAsync();

            return Ok(data);
        }

        [HttpGet("{id}")]
        public async Task<IActionResult> GetDetail(int id)
        {
            // 这里的 Select 确保前端能拿到所有播放字段
            var anime = await _db.Animes
                .AsNoTracking()
                .Select(x => new { x.Id, x.Title, x.PlayUrls, x.BackupUrls })
                .FirstOrDefaultAsync(x => x.Id == id);

            return anime == null ? NotFound() : Ok(anime);
        }

        // https://localhost:8060/api/netflix/maintenance/flush-jinying
        [HttpGet("maintenance/flush-jinying")]
        /// <summary>
        /// 【临时】修复：定义 PlayUrls = 金鹰，BackupUrls = 红牛，没有 m3u8 的补齐
        /// </summary>
        /// <returns></returns>
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
        [HttpGet("export-for-manus")]
        /// <summary>
        /// 【临时】“全量导出”接口，找manus拉
        /// </summary>
        /// <returns></returns>
        public async Task<IActionResult> ExportForManus()
        {
            var allData = await _db.Animes
                .AsNoTracking()
                .Select(x => new
                {
                    // 把 [第xx集]、[OVA]、[剧场版] 等全部去掉
                    Title = Regex.Replace(x.Title, @"\s*\[.*?\]", "").Trim(),
                    Title_JP = "", // 番剧日文原名
                    CoverFile = "", // 封面文件名
                })
                .ToListAsync();

            return Ok(allData);
        }

        // https://localhost:8060/api/netflix/export-seed
        [HttpGet("export-seed")]
        /// <summary>
        /// 【常驻】到出 SQL 成 json，迁移备份
        /// </summary>
        /// <remarks>
        /// 调用后会在项目目录生成 seed.json 文件，包含所有动漫信息。
        /// 新部署时 Program.cs 会自动读取这个文件进行 Seed 操作。
        /// </remarks>
        /// <returns>导出结果</returns>
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
    }
}