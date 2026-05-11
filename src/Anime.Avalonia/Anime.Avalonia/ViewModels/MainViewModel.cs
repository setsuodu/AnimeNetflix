using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace Anime.Avalonia.ViewModels;

public partial class MainViewModel : ViewModelBase
{
    private readonly HttpClient _httpClient = new HttpClient();

    [ObservableProperty] private ObservableCollection<AnimeModel> _animes = new();
    [ObservableProperty] private string _status = "点击上方按钮开始加载...";
    [ObservableProperty] private string _searchText = string.Empty;
    [ObservableProperty] private bool _isLoading = false;     // ← 新增

    public MainViewModel()
    {
        Debug.WriteLine("🏗️ MainViewModel 初始化");
    }

    [RelayCommand]
    private async Task LoadAnimesAsync()
    {
        IsLoading = true;
        Status = "正在请求...";

        try
        {
            string baseUrl = "http://192.168.1.198:8060";   // 你的地址
            string url = $"{baseUrl}/api/netflix?page=1&pageSize=60&search={SearchText ?? ""}";

            var response = await _httpClient.GetAsync(url);
            response.EnsureSuccessStatusCode();

            var json = await response.Content.ReadAsStringAsync();
            var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            var list = JsonSerializer.Deserialize<List<AnimeModel>>(json, options);

            // 加上这行调试打印，在控制台一眼就能看到数据对不对
            if (list != null && list.Count > 0)
            {
                Debug.WriteLine($"✅ 第一部番剧名字: {list[0].Title}");
            }

            Animes.Clear();
            if (list != null && list.Count > 0)
            {
                foreach (var item in list)
                    Animes.Add(item);

                // 这样写最稳：既显示总数，又抓出 Title 是否为 null
                var firstTitle = Animes[0].Title ?? "⚠️ Title字段为Null(检查大小写或AnimeModel定义)";
                Status = $"共{Animes.Count}部。第一部：{firstTitle}";
            }
            else
            {
                Status = "加载完成，但返回列表为空。";
            }
        }
        catch (Exception ex)
        {
            Status = $"请求失败: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }
}