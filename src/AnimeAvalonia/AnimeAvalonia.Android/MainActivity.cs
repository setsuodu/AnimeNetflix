using Android.App;
using Android.Content.PM;
using Avalonia;
using Avalonia.Android;

namespace AnimeAvalonia.Android;

[Activity(
    Label = "AnimeNetflix",
    Theme = "@style/MyTheme.NoActionBar",
    Icon = "@drawable/icon",
    MainLauncher = true,
    ConfigurationChanges = ConfigChanges.Orientation | ConfigChanges.ScreenSize | ConfigChanges.UiMode)]
public class MainActivity : AvaloniaMainActivity   // ← 这里去掉 <App>
{
    // CustomizeAppBuilder 已经不需要在这里写了（移到 Application 类里）
}