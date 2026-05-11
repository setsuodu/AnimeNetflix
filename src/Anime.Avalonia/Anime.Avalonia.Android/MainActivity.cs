using Android.App;
using Android.Content.PM;
using Avalonia;
using Avalonia.Android;

namespace Anime.Avalonia.Android;

[Activity(
    // 强制指定一个名称，防止混淆或改名导致的闪退
    Name = "com.setsuodu.animenetflix.MainActivity", 
    Label = "AnimeNetflix",
    Theme = "@style/MyTheme.NoActionBar",
    Icon = "@drawable/icon",
    MainLauncher = true,
    ConfigurationChanges = ConfigChanges.Orientation | ConfigChanges.ScreenSize | ConfigChanges.UiMode)]
public class MainActivity : AvaloniaMainActivity
{
}