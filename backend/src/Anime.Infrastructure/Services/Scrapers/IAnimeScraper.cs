namespace Anime.Infrastructure.Services.Scrapers;

// 纯接口，定义爬虫必须实现的三个动作
public interface IAnimeScraper
{
    // 拿总页数
    int ParseTotalPage(string html);

    // 拿目录列表
    List<ScrapedAnimeModel> ParseList(string html);

    // 强制接收标准地区名称进行直接赋值
    ScrapedDetailModel ParseDetail(string html, string area);
}