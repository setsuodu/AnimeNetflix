using Anime.Infrastructure;
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

        // https://localhost:8060/api/collector/run
        /// <summary>
        /// 开始爬取金鹰资源|日本动画
        /// </summary>
        /// <returns></returns>
        [HttpGet("run")]
        public async Task<IActionResult> Run()   // 改成 async Task 更好
        {
            Console.WriteLine("测试爬虫");

            string urlTemplate = "https://jinyingzy.net/index.php/vod/type/id/25/page/{0}.html?ac=detail";

            // 更安全的 fire-and-forget
            _ = Task.Run(async () =>
            {
                try
                {
                    await _crawler.Run(_scraper, urlTemplate);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"【后台任务异常】{ex.Message}");
                    Console.WriteLine(ex.ToString());
                }
            });

            Console.WriteLine("点火成功，爬虫已在后台运行");
            //return Ok(new { message = "点火成功，爬虫已在后台运行", target = urlTemplate });
            return Ok(new
            {
                message = "点火成功",
                startTime = DateTime.Now.ToString("HH:mm:ss"),
                status = "Stopwatch 已在后台 service 启动"
            });
        }
    }
}