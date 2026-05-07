namespace Anime.Infrastructure.Services.Scrapers;

// 纯接口，定义爬虫必须实现的三个动作
public interface IAnimeScraper
{
    // 拿总页数
    int ParseTotalPage(string html);

    // 拿目录列表
    List<ScrapedAnimeModel> ParseList(string html);

    // 拿详情页所有数据（从元组升级为 Model，支持分类和年代）
    ScrapedDetailModel ParseDetail(string html);
}