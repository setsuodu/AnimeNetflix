using Anime.Infrastructure.Context;
using Anime.Infrastructure.Entities;
using Anime.Infrastructure.Services.Scrapers;
using Microsoft.EntityFrameworkCore;
using System.Diagnostics;
using System.Text.RegularExpressions;

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

    // 核心改造 1：Run 方法显式接收 targetArea，并为了向下兼容保持 fullCrawl 的默认值
    public async Task Run(IAnimeScraper scraper, string urlTemplate, string targetArea, bool fullCrawl = false)
    {
        var sw = Stopwatch.StartNew();
        int skipCount = 0;
        try
        {
            Console.WriteLine($"【爬虫点火】目标分类: {targetArea}，开始时间: {DateTime.Now:HH:mm:ss}，全量抓取: {fullCrawl}");

            _http.Timeout = TimeSpan.FromMinutes(10);
            var firstPageHtml = await _http.GetStringAsync(string.Format(urlTemplate, 1));
            int total = scraper.ParseTotalPage(firstPageHtml);

            for (int i = 1; i <= total; i++)
            {
                var listHtml = (i == 1) ? firstPageHtml : await _http.GetStringAsync(string.Format(urlTemplate, i));
                var items = scraper.ParseList(listHtml);

                Console.WriteLine($"【爬虫】第 {i}/{total} 页解析到 {items.Count} 条数据");

                foreach (var item in items)
                {
                    using var db = _dbFactory.CreateDbContext();

                    var detailHtml = await _http.GetStringAsync(item.DetailUrl);

                    // 核心改造 2：把上层控制器传进来的国家字符串，直接砸给详情解析器！
                    var detail = scraper.ParseDetail(detailHtml, targetArea);

                    var (baseTitle, episodePart) = SplitTitle(item.Title);

                    var existing = await db.Animes.FirstOrDefaultAsync(a => a.SourceFingerprint == item.Fingerprint);

                    if (existing != null)
                    {
                        bool hasNewContent = false;

                        if (detail.SiteUpdateTime.HasValue)
                        {
                            if (!existing.SiteUpdateTime.HasValue || detail.SiteUpdateTime > existing.SiteUpdateTime)
                                hasNewContent = true;
                        }
                        else if (episodePart != existing.Episodes)
                        {
                            hasNewContent = true;
                        }

                        // 强制覆盖兜底逻辑：如果你是在做全量跑（fullCrawl = true），或者现有库里的 Area 是空的，也视为需要更新
                        if (string.IsNullOrWhiteSpace(existing.Area))
                        {
                            hasNewContent = true;
                        }

                        if (hasNewContent)
                        {
                            existing.Title = baseTitle;
                            existing.Episodes = episodePart;
                            existing.PlayUrls = detail.Play1;
                            existing.BackupUrls = detail.Play2 ?? string.Empty;
                            existing.Year = detail.Year;

                            // 更新区域（此处 detail.Area 必定不为空，因为 Scraper 里面已经做了兜底）
                            existing.Area = detail.Area;
                            existing.Category = detail.Category;
                            existing.SiteUpdateTime = detail.SiteUpdateTime;
                            existing.UpdateTime = DateTime.UtcNow;

                            await db.SaveChangesAsync();
                            Console.WriteLine($"[更新/兜底] {baseTitle} | 地区: {existing.Area}");
                            skipCount = 0;
                        }
                        else
                        {
                            existing.UpdateTime = DateTime.UtcNow;
                            await db.SaveChangesAsync();
                            Console.WriteLine($"[跳过] {baseTitle}");

                            if (!fullCrawl)
                            {
                                skipCount++;
                                if (skipCount >= 5)
                                {
                                    Console.WriteLine($"【爬虫】连续5个跳过，提前结束");
                                    sw.Stop();
                                    Console.WriteLine($"【爬虫完成】总耗时 {sw.Elapsed.TotalSeconds:F2} 秒");
                                    return;
                                }
                            }
                        }
                    }
                    else
                    {
                        db.Animes.Add(new AnimeInfo
                        {
                            SourceFingerprint = item.Fingerprint,
                            Title = baseTitle,
                            Episodes = episodePart,
                            JapaneseTitle = string.Empty,
                            EnglishTitle = string.Empty,
                            PlayUrls = detail.Play1,
                            BackupUrls = detail.Play2 ?? string.Empty,
                            Year = detail.Year,

                            // 新增入库区域
                            Area = detail.Area,
                            Category = detail.Category,
                            UpdateTime = DateTime.UtcNow,
                            SiteUpdateTime = detail.SiteUpdateTime
                        });

                        await db.SaveChangesAsync();
                        Console.WriteLine($"[入库] {baseTitle} | 地区: {detail.Area}");
                        skipCount = 0;
                    }
                }
            }

            sw.Stop();
            Console.WriteLine($"【爬虫完成】总耗时 {sw.Elapsed.TotalSeconds:F2} 秒");
        }
        catch (Exception ex)
        {
            sw.Stop();
            Console.WriteLine($"【爬虫异常】耗时 {sw.Elapsed.TotalSeconds:F2} 秒: {ex.Message}");
        }
    }

    private static (string BaseTitle, string EpisodePart) SplitTitle(string fullTitle)
    {
        if (string.IsNullOrWhiteSpace(fullTitle))
            return (string.Empty, string.Empty);

        var regex = new Regex(@"(\s*\[第.*?集.*?\]|\s*\[完结?\]|\s*\[.*?版.*?\])", RegexOptions.IgnoreCase);
        var match = regex.Match(fullTitle);

        if (match.Success)
        {
            string baseTitle = fullTitle.Substring(0, match.Index).Trim();
            string episodePart = match.Value.Trim();
            baseTitle = Regex.Replace(baseTitle, @"\s+", " ").Trim();
            return (baseTitle, episodePart);
        }

        return (fullTitle.Trim(), "");
    }
}