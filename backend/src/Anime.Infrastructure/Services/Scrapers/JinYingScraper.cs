using System.Text.RegularExpressions;
using HtmlAgilityPack;

namespace Anime.Infrastructure.Services.Scrapers;

public class JinYingScraper : IAnimeScraper
{
    public int ParseTotalPage(string html)
    {
        var doc = new HtmlDocument();
        doc.LoadHtml(html);

        // 优先从“当前1/46页”这种文字里提取（最可靠）
        var textMatch = Regex.Match(doc.DocumentNode.InnerText, @"当前\s*\d+/\s*(\d+)\s*页");
        if (textMatch.Success && int.TryParse(textMatch.Groups[1].Value, out int pageCount))
            return pageCount;

        // 备选：找所有 page/数字 链接里最大的页码
        var links = doc.DocumentNode.SelectNodes("//a[contains(@href, '/page/')]");
        if (links != null)
        {
            int maxPage = 1;
            foreach (var link in links)
            {
                var m = Regex.Match(link.GetAttributeValue("href", ""), @"page/(\d+)");
                if (m.Success && int.TryParse(m.Groups[1].Value, out int p) && p > maxPage)
                    maxPage = p;
            }
            if (maxPage > 1) return maxPage;
        }

        // 最后兜底：找末页按钮
        var lastBtn = doc.DocumentNode.SelectSingleNode("//a[contains(text(),'尾页') or contains(text(),'末页')]");
        if (lastBtn != null)
        {
            var m = Regex.Match(lastBtn.GetAttributeValue("href", ""), @"page/(\d+)");
            if (m.Success) return int.Parse(m.Groups[1].Value);
        }

        Console.WriteLine("【警告】无法解析总页数，默认1页");
        return 1;
    }

    public List<ScrapedAnimeModel> ParseList(string html)
    {
        var doc = new HtmlDocument();
        doc.LoadHtml(html);
        var results = new List<ScrapedAnimeModel>();

        // 更宽松的写法：只要有 xing_vb4 的链接就拿
        var linkNodes = doc.DocumentNode.SelectNodes("//span[@class='xing_vb4']/a");

        if (linkNodes == null) return results;

        foreach (var aTag in linkNodes)
        {
            var href = aTag.GetAttributeValue("href", "");
            if (string.IsNullOrEmpty(href)) continue;

            results.Add(new ScrapedAnimeModel
            {
                Title = aTag.InnerText.Trim(),
                Fingerprint = Regex.Match(href, @"id/(\d+)").Groups[1].Value,
                DetailUrl = "https://jinyingzy.net" + href
            });
        }

        Console.WriteLine($"【爬虫】本页解析到 {results.Count} 条数据");
        return results;
    }

    public ScrapedDetailModel ParseDetail(string html)
    {
        var doc = new HtmlDocument();
        doc.LoadHtml(html);
        var res = new ScrapedDetailModel();

        var p1Nodes = doc.DocumentNode.SelectNodes("//div[@id='play_1']//li")?.Select(n => n.InnerText.Trim());

        res.Play1 = CleanJinYingUrls(p1Nodes);
        res.Play2 = string.Empty; // 强制清空 BackupUrls

        var infoNodes = doc.DocumentNode.SelectNodes("//div[@class='vodinfobox']//li");
        if (infoNodes != null)
        {
            foreach (var node in infoNodes)
            {
                var text = node.InnerText.Trim();
                if (text.Contains("上映："))
                {
                    var yearMatch = Regex.Match(text, @"\d{4}");
                    res.Year = yearMatch.Success ? int.Parse(yearMatch.Value) : 0;
                }
                if (text.Contains("地区：")) res.Area = text.Replace("地区：", "").Trim();
                if (text.Contains("类型：")) res.Category = text.Replace("类型：", "").Trim();
            }
        }
        return res;
    }
    // 专门处理金鹰播放地址的私有辅助函数
    private string CleanJinYingUrls(IEnumerable<string>? nodes)
    {
        if (nodes == null) return string.Empty;

        var cleaned = nodes.Select(ep =>
        {
            if (!ep.Contains("$")) return ep;

            var parts = ep.Split('$');
            var name = parts[0];
            var url = parts[1].Trim();

            if (url.Contains("ijycnd.com/play/") && !url.EndsWith(".m3u8"))
            {
                url = $"{url}/index.m3u8";
            }
            return $"{name}${url}";
        });

        return string.Join("#", cleaned);
    }
}