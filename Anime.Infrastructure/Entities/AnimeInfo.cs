using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace Anime.Infrastructure.Entities
{
    public class AnimeInfo
    {
        [Key]
        public int Id { get; set; }

        [Required]
        [MaxLength(200)]
        public string Title { get; set; } = string.Empty;

        [MaxLength(200)]
        public string JapaneseTitle { get; set; } = string.Empty;   // ← 新增：日文名

        [MaxLength(200)]
        public string EnglishTitle { get; set; } = string.Empty;    // ← 新增：英文名

        // 在 AnimeInfo.cs 中添加
        public string CoverUrl { get; set; } = string.Empty;

        // 对应代码里的 SourceFingerprint，用来存 ID 或 Hash，做唯一索引
        [Required]
        [MaxLength(100)]
        public string SourceFingerprint { get; set; } = string.Empty;

        [Column(TypeName = "text")] // 用 text 类型，防止集数太多超长
        public string PlayUrls { get; set; } = string.Empty; // 金鹰源，必须 m3u8 结尾

        [Column(TypeName = "text")]
        public string BackupUrls { get; set; } = string.Empty; // 红牛源，必须 m3u8 结尾

        // --- 新增：多维度筛选字段 ---
        public int Year { get; set; } // 存储年份（如 2026）

        [MaxLength(50)]
        public string Area { get; set; } = string.Empty; // 存储地区（如 日本）

        [MaxLength(100)]
        public string Category { get; set; } = string.Empty; // 存储类型（如 剧情/科幻）

        public DateTime UpdateTime { get; set; }
    }
}