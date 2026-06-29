using Microsoft.EntityFrameworkCore;
using Anime.Infrastructure.Entities; // 引用你 Entities 里的模型

// 这里的 namespace 必须带上 .Context，和你老项目保持一致
namespace Anime.Infrastructure.Context;

public class AnimeDbContext : DbContext
{
    public AnimeDbContext(DbContextOptions<AnimeDbContext> options) : base(options)
    {
    }

    // 数据库表
    public DbSet<AnimeInfo> Animes => Set<AnimeInfo>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // 建立索引，方便前端检索
        modelBuilder.Entity<AnimeInfo>(entity =>
        {
            entity.HasKey(e => e.SourceFingerprint);  // 显式声明

            entity.HasIndex(e => e.Title).HasDatabaseName("Index_Anime_Title");
            entity.Property(e => e.PlayUrls).HasColumnType("text");
        });
    }
}