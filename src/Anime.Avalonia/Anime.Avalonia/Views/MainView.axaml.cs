using Avalonia.Controls;
using Avalonia.Input;
using Anime.Avalonia.ViewModels;

namespace Anime.Avalonia.Views;

public partial class MainView : UserControl
{
    public MainView()
    {
        InitializeComponent();
        DataContext = new MainViewModel();
    }

    // 单个卡片点击（恢复了）
    private void OnAnimeClicked(object sender, PointerPressedEventArgs e)
    {
        if (sender is Border border && border.DataContext is AnimeModel anime)
        {
            // TODO: 以后打开详情页
            System.Diagnostics.Debug.WriteLine($"点击了番剧: {anime.Title}");
        }
    }
}