using Anime.Infrastructure.Context;
using Anime.Infrastructure.Entities;
using Anime.Infrastructure.Services.Scrapers;
using Microsoft.EntityFrameworkCore;
using System.Diagnostics;

namespace Anime.Infrastructure.Services;

public class CrawlerService
{
    private readonly IDbContextFactory<AnimeDbContext> _dbFactory;
    private readonly HttpClient _http;

    public CrawlerService(IDbContextFactory<AnimeDbContext> dbFactory, HttpClient http)
    {
        _dbFactory = dbFactory;
        _http = http;
    }

    public async Task Run(IAnimeScraper scraper, string urlTemplate)
    {
        var sw = Stopwatch.StartNew(); // 开始计时
        try
        {
            Console.WriteLine($"【爬虫点火】开始时间: {DateTime.Now:HH:mm:ss}");

            _http.Timeout = TimeSpan.FromMinutes(10);
            var firstPageHtml = await _http.GetStringAsync(string.Format(urlTemplate, 1));
            int total = scraper.ParseTotalPage(firstPageHtml);

            for (int i = 1; i <= total; i++)
            {
                var listHtml = (i == 1) ? firstPageHtml : await _http.GetStringAsync(string.Format(urlTemplate, i));
                var items = scraper.ParseList(listHtml);

                foreach (var item in items)
                {
                    using var db = _dbFactory.CreateDbContext();

                    // 1. 根据指纹查找现有记录
                    var existing = await db.Animes.FirstOrDefaultAsync(a => a.SourceFingerprint == item.Fingerprint);

                    // 2. 爬取详情页（获取最新标题、剧集、分类等）
                    var detailHtml = await _http.GetStringAsync(item.DetailUrl);
                    var detail = scraper.ParseDetail(detailHtml);

                    if (existing != null)
                    {
                        // --- 发现老数据：执行覆盖更新，同步标题和集数 ---
                        existing.Title = item.Title;      // 关键：[第4集] 变 [第5集]
                        existing.PlayUrls = detail.Play1;
                        existing.BackupUrls = detail.Play2;

                        // 同步新增的筛选字段
                        existing.Year = detail.Year;
                        existing.Area = detail.Area;
                        existing.Category = detail.Category;

                        existing.UpdateTime = DateTime.UtcNow;

                        await db.SaveChangesAsync();
                        Console.WriteLine($"[更新] {item.Title}");
                    }
                    else
                    {
                        // --- 发现新数据：执行入库 ---
                        db.Animes.Add(new AnimeInfo
                        {
                            Title = item.Title,
                            SourceFingerprint = item.Fingerprint,
                            PlayUrls = detail.Play1,
                            BackupUrls = detail.Play2 ?? string.Empty, // 满足 NOT NULL 约束
                            Year = detail.Year,
                            Area = detail.Area,
                            Category = detail.Category,
                            UpdateTime = DateTime.UtcNow
                        });

                        await db.SaveChangesAsync();
                        Console.WriteLine($"[入库] {item.Title}");
                    }
                }
            }
            //Console.WriteLine("【爬虫】执行完毕！");
            sw.Stop();
            Console.WriteLine($"【爬虫点火】执行完毕！总计耗时: {sw.Elapsed.TotalSeconds:F2} 秒");
        }
        catch (Exception ex)
        {
            //Console.WriteLine("【爬虫异常】" + ex.Message);
            sw.Stop();
            Console.WriteLine($"【爬虫异常】耗时 {sw.Elapsed.TotalSeconds:F2} 秒后发生错误: {ex.Message}");
        }
    }
}