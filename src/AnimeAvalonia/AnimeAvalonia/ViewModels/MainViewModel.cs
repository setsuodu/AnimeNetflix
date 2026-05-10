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
    private readonly HttpClient _http = new() { BaseAddress = new Uri("http://10.0.2.2:7153/") }; // 模拟器访问主机用 10.0.2.2

    [ObservableProperty]
    private ObservableCollection<AnimeInfo> _animeList = new();

    [ObservableProperty]
    private AnimeInfo? _selectedAnime;

    [RelayCommand]
    private async Task Refresh()
    {
        try
        {
            var list = await _http.GetFromJsonAsync<AnimeInfo[]>("api/netflix/list")
                       ?? Array.Empty<AnimeInfo>();
            AnimeList.Clear();
            foreach (var item in list) AnimeList.Add(item);
        }
        catch (Exception ex)
        {
            // TODO: 加个提示 Toast 或 Dialog
            Console.WriteLine("加载失败: " + ex.Message);
        }
    }

    public MainViewModel()
    {
        RefreshCommand.Execute(null); // 启动时自动刷新
    }
}

public class AnimeInfo
{
    public string? Title { get; set; }
    public string? CoverUrl { get; set; }
    public string? LatestEpisode { get; set; }
    public string? M3u8Url { get; set; }
}