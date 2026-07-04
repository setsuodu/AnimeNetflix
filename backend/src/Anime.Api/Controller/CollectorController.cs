using Anime.Infrastructure.Services;
using Anime.Infrastructure.Services.Scrapers;
using Microsoft.AspNetCore.Mvc;

namespace Anime.Api.Controllers
{
    [ApiController]
    [Route("api/collector")]
    public class CollectorController : ControllerBase
    {
        private readonly CrawlerService _crawler;
        private readonly IAnimeScraper _scraper;

        public CollectorController(CrawlerService crawler, IAnimeScraper scraper)
        {
            _crawler = crawler;
            _scraper = scraper;
        }

        // =========================================================================
        // 支持全量点火的终极接口：
        // 增量抓中国动漫：https://localhost:8060/api/collector/run?id=24
        // 全量刷中国动漫：https://localhost:8060/api/collector/run?id=24&isFull=true
        // =========================================================================
        /// <summary>
        /// 开始爬取金鹰资源动漫数据（支持按ID指定Area与全量/增量模式）
        /// </summary>
        /// <param name="id">网页分类ID (24=中国, 25=日本, 26=美国)</param>
        /// <param name="isFull">是否开启全量爬取（true=遇到重复不跳过，强行覆盖更新；false=默认增量）</param>
        [HttpGet("run")]
        public async Task<IActionResult> Run([FromQuery] int id = 25, [FromQuery] bool isFull = false)
        {
            if (id != 24 && id != 25 && id != 26)
            {
                return BadRequest("不支持的分类ID。请使用: 24(中国), 25(日本), 26(美国)");
            }

            // 根据传入的 id 铁证，锁定标准的 Area 字段字符串
            string area = id switch
            {
                24 => "中国",
                25 => "日本",
                26 => "美国",
                _ => "未知"
            };

            Console.WriteLine($"【爬虫全面点火】分类ID: {id} -> 对应Area: {area} | 模式: {(isFull ? "🔥全量强刷" : "⚡增量更新")}");

            string urlTemplate = $"https://jinyingzy.net/index.php/vod/type/id/{id}/page/{{0}}.html?ac=detail";

            // 完美的后台线程挂载，直接把 area 和 isFull (对应 CrawlerService 的 fullCrawl) 干净投递进去
            _ = Task.Run(async () =>
            {
                try
                {
                    // 参数完美对齐：_crawler.Run(scraper, urlTemplate, area, fullCrawl)
                    await _crawler.Run(_scraper, urlTemplate, area, isFull);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"【后台任务异常】ID={id} | {ex.Message}");
                    Console.WriteLine(ex.ToString());
                }
            });

            return Ok(new
            {
                message = "点火成功，爬虫任务已在后台丝滑运行",
                targetArea = area,
                crawlMode = isFull ? "FullCrawl (全量不跳过)" : "Incremental (增量跳过)",
                startTime = DateTime.Now.ToString("HH:mm:ss")
            });
        }
    }
}