using Anime.Infrastructure.Context;
using Anime.Infrastructure.Entities;
using Anime.Infrastructure.Services;
using Anime.Infrastructure.Services.Scrapers;
using Microsoft.EntityFrameworkCore;
using Microsoft.OpenApi;
using System.Text.Json;

var builder = WebApplication.CreateBuilder(args);

var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");

builder.Services.AddHttpClient<CrawlerService>(client => client.Timeout = TimeSpan.FromMinutes(5));
builder.Services.AddSingleton<CrawlerService>();
builder.Services.AddScoped<IAnimeScraper, JinYingScraper>();

builder.Services.AddDbContextFactory<AnimeDbContext>(options =>
    options.UseNpgsql(connectionString));

builder.Services.AddControllers();

// ==================== Swashbuckle 10.1.7 配置 ====================
builder.Services.AddEndpointsApiExplorer();

builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "AnimeNetflix 自宅影院 API",
        Version = "v1",
        Description = "金鹰资源爬虫 + 前端影院接口",
        Contact = new OpenApiContact
        {
            Name = "うなみ",
            Url = new Uri("https://github.com/setsuodu/AnimeNetflix")
        }
    });

    // 按 Controller 分组，像 Postman 文件夹
    options.TagActionsBy(api =>
    {
        var controller = api.ActionDescriptor.RouteValues["controller"] ?? "Default";
        return new[] { controller };   // ← 必须是数组
    });

    options.OrderActionsBy(apiDesc =>
        $"{apiDesc.ActionDescriptor.RouteValues["controller"]}_{apiDesc.RelativePath}");
});
// ===========================================================

var app = builder.Build();

// ====================== 数据库迁移 + Seed ======================
using (var scope = app.Services.CreateScope())
{
    var services = scope.ServiceProvider;
    var context = services.GetRequiredService<AnimeDbContext>();
    var logger = services.GetRequiredService<ILogger<Program>>();   // 推荐用 logger

    try
    {
        // 1. 迁移数据库
        logger.LogInformation("🚀 Applying database migrations...");
        await context.Database.MigrateAsync();

        // 2. 检查是否需要 Seed
        if (!await context.Animes.AnyAsync())
        {
            string seedPath = Path.Combine(AppContext.BaseDirectory, "seed.json");

            if (File.Exists(seedPath))
            {
                logger.LogInformation($"🌱 Found seed.json, start seeding... ({seedPath})");

                var jsonData = await File.ReadAllTextAsync(seedPath);

                var options = new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                };

                var data = JsonSerializer.Deserialize<List<AnimeInfo>>(jsonData, options);

                if (data?.Count > 0)
                {
                    await context.Animes.AddRangeAsync(data);
                    await context.SaveChangesAsync();

                    logger.LogInformation($"✅ 成功从 seed.json 导入 {data.Count} 条动漫数据！");
                }
                else
                {
                    logger.LogWarning("⚠️ seed.json 解析后数据为空");
                }
            }
            else
            {
                logger.LogWarning("⚠️ seed.json 文件未找到！");
            }
        }
        else
        {
            logger.LogInformation("✅ 数据库已有数据，跳过 seeding");
        }
    }
    catch (Exception ex)
    {
        logger.LogError(ex, "❌ 迁移或 Seeding 过程中发生错误");
        // 可以选择 throw; 让程序启动失败（推荐生产环境）
    }
}
// ============================================================

app.UseDefaultFiles();
app.UseStaticFiles();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();

    app.UseReDoc(options =>
    {
        options.RoutePrefix = "redoc";
        options.SpecUrl = "/swagger/v1/swagger.json";
        options.DocumentTitle = "AnimeNetflix API 文档";
    });
}

app.MapControllers();
app.Run();