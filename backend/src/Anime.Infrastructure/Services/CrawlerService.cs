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

    public async Task Run(IAnimeScraper scraper, string urlTemplate)
    {
        var sw = Stopwatch.StartNew();
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

                Console.WriteLine($"【爬虫】第 {i}/{total} 页解析到 {items.Count} 条数据");

                foreach (var item in items)
                {
                    using var db = _dbFactory.CreateDbContext();

                    var detailHtml = await _http.GetStringAsync(item.DetailUrl);
                    var detail = scraper.ParseDetail(detailHtml);

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
                        else if (episodePart.Length > existing.Episodes.Length)
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
                            existing.Area = detail.Area;
                            existing.Category = detail.Category;
                            existing.SiteUpdateTime = detail.SiteUpdateTime;
                            existing.UpdateTime = DateTime.UtcNow;

                            await db.SaveChangesAsync();
                            Console.WriteLine($"[更新] {baseTitle}");
                        }
                        else
                        {
                            existing.UpdateTime = DateTime.UtcNow;
                            await db.SaveChangesAsync();
                            Console.WriteLine($"[跳过] {baseTitle}");
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
                            Area = detail.Area,
                            Category = detail.Category,
                            UpdateTime = DateTime.UtcNow,
                            SiteUpdateTime = detail.SiteUpdateTime
                        });

                        await db.SaveChangesAsync();
                        Console.WriteLine($"[入库] {baseTitle}");
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