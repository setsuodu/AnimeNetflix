namespace Anime.Infrastructure.Services.Scrapers;

// 1. 列表页模型：只存最基础的索引信息
public class ScrapedAnimeModel
{
    public string Title { get; set; } = string.Empty;
    public string Fingerprint { get; set; } = string.Empty;
    public string DetailUrl { get; set; } = string.Empty;
}

// 2. 详情页模型：承载所有深度数据，传回给 Service
public class ScrapedDetailModel
{
    public string Play1 { get; set; } = string.Empty;
    public string Play2 { get; set; } = string.Empty;
    public int Year { get; set; }
    public string Area { get; set; } = string.Empty;
    public string Category { get; set; } = string.Empty;
    public string Cover { get; set; } = string.Empty;
    public DateTime? SiteUpdateTime { get; set; }          // 纯增量对比字段
}
