using Anime.Avalonia.ViewModels;
using Anime.Infrastructure.Entities;
using Avalonia.Controls;
using Avalonia.Interactivity;
using LibVLCSharp.Avalonia;
using LibVLCSharp.Shared;

namespace Anime.Avalonia.Views;

public partial class DetailPage : UserControl
{
    private readonly DetailPageViewModel _vm;

    public DetailPage(int animeId, LibVLC libVLC)
    {
        InitializeComponent();

        _vm = new DetailPageViewModel(libVLC);
        DataContext = _vm;

        // 绑定 VideoView（必须和 XAML 里的 x:Name 一致）
        if (VideoView != null)
            VideoView.MediaPlayer = _vm.MediaPlayer;

        Loaded += async (_, _) => await _vm.LoadAnimeAsync(animeId);
    }

    private void Back_Click(object sender, RoutedEventArgs e)
    {
        // 返回上一页
    }

    private void SwitchMain_Click(object sender, RoutedEventArgs e)
    {
        _vm.SwitchToMain();
    }

    private void SwitchBackup_Click(object sender, RoutedEventArgs e)
    {
        _vm.SwitchToBackup();
    }

    // 确保这两个方法名也和 XAML 里的 SwitchSource1/2 一致
    private void SwitchSource1(object sender, RoutedEventArgs e) => _vm.SwitchToMain();
    private void SwitchSource2(object sender, RoutedEventArgs e) => _vm.SwitchToBackup();

    // 必须添加这个方法，否则点击剧集会报错
    private void PlayEpisode_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.Tag is string url)
        {
            // 调用 ViewModel 执行播放逻辑
            _vm.PlayUrl(url);
        }
    }
}