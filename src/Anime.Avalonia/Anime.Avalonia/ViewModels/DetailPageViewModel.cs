using Anime.Infrastructure.Entities;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using LibVLCSharp.Shared;
using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading.Tasks;

namespace Anime.Avalonia.ViewModels;

public partial class DetailPageViewModel : ObservableObject
{
    private readonly LibVLC _libVLC;
    private readonly MediaPlayer _mediaPlayer;
    private readonly HttpClient _http = new();

    [ObservableProperty] private string title = "加载中...";

    public ObservableCollection<Episode> Episodes { get; } = new();

    private AnimeInfo? _currentAnime;

    public DetailPageViewModel(LibVLC libVLC)
    {
        _libVLC = libVLC;
        _mediaPlayer = new MediaPlayer(_libVLC);
    }

    public MediaPlayer MediaPlayer => _mediaPlayer;

    [RelayCommand]
    public async Task LoadAnimeAsync(int animeId)
    {
        try
        {
            _currentAnime = await _http.GetFromJsonAsync<AnimeInfo>(
                $"http://localhost:5041/api/netflix/{animeId}");   // ← 改成你实际端口

            if (_currentAnime == null) return;

            Title = _currentAnime.Title;

            LoadEpisodes(_currentAnime.PlayUrls);   // 默认主线路
        }
        catch (Exception ex)
        {
            Title = "加载失败: " + ex.Message;
        }
    }

    private void LoadEpisodes(string rawUrls)
    {
        Episodes.Clear();
        if (string.IsNullOrWhiteSpace(rawUrls)) return;

        var eps = rawUrls.Split('#', StringSplitOptions.RemoveEmptyEntries)
            .Select(x =>
            {
                var p = x.Split('$');
                return new Episode
                {
                    Name = p.Length > 0 ? p[0].Trim() : "未知",
                    Url = p.Length > 1 ? p[1].Trim() : ""
                };
            });

        foreach (var ep in eps) Episodes.Add(ep);

        if (Episodes.Count > 0)
            PlayEpisode(Episodes[0]);
    }

    [RelayCommand]
    public void PlayEpisode(Episode ep)
    {
        if (string.IsNullOrWhiteSpace(ep?.Url)) return;

        var media = new Media(_libVLC, new Uri(ep.Url));
        _mediaPlayer.Media = media;
        _mediaPlayer.Play();
    }

    // 在 DetailPageViewModel 类中添加
    public void PlayUrl(string url)
    {
        if (string.IsNullOrEmpty(url)) return;

        // 使用 VLC 播放器加载新媒体
        MediaPlayer.Media = new Media(_libVLC, new Uri(url));
        MediaPlayer.Play();
    }

    public void SwitchToMain() => LoadEpisodes(_currentAnime?.PlayUrls ?? "");
    public void SwitchToBackup() => LoadEpisodes(_currentAnime?.BackupUrls ?? "");
}