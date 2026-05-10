using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using System;
using System.Collections.ObjectModel;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;

namespace AnimeAvalonia.ViewModels;

public partial class MainViewModel : ViewModelBase
{
    // ==================== 改这里 ====================
    private readonly HttpClient _http = new()
    {
        BaseAddress = new Uri("http://192.168.1.198:8060/"),   // ← 确认这个IP对不对
        Timeout = TimeSpan.FromSeconds(20)
    };
    // ===============================================

    [ObservableProperty]
    private ObservableCollection<AnimeInfo> animeList = new();

    [ObservableProperty]
    private AnimeInfo? selectedAnime;

    [RelayCommand]
    private async Task Refresh()
    {
        Console.WriteLine("=== 开始刷新列表 ===");
        try
        {
            var url = _http.BaseAddress + "api/netflix/list";
            Console.WriteLine($"正在请求: {url}");

            var list = await _http.GetFromJsonAsync<AnimeInfo[]>("api/netflix/list");

            Console.WriteLine($"✅ 成功获取 {list?.Length ?? 0} 条数据");

            AnimeList.Clear();
            if (list != null)
            {
                foreach (var item in list)
                    AnimeList.Add(item);
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ 请求失败: {ex.Message}");
            Console.WriteLine(ex.ToString());
        }
    }

    public MainViewModel()
    {
        _ = Refresh();   // 启动时自动刷新
    }
}

public class AnimeInfo
{
    public string? Title { get; set; }
    public string? CoverUrl { get; set; }
    public string? LatestEpisode { get; set; }
}