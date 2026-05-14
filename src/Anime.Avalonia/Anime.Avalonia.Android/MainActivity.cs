using Android.App;
using Android.Content.PM;
using Avalonia;
using Avalonia.Android;
using Avalonia.Media;
using System;

namespace Anime.Avalonia.Android;

[Activity(
    Label = "Anime.Avalonia.Android",
    Theme = "@style/MyTheme.NoActionBar",
    Icon = "@drawable/icon",
    MainLauncher = true,
    ConfigurationChanges = ConfigChanges.Orientation | ConfigChanges.ScreenSize | ConfigChanges.UiMode)]
public class MainActivity : AvaloniaMainActivity<App>
{
    public static MainActivity? Instance { get; private set; }

    protected override AppBuilder CustomizeAppBuilder(AppBuilder builder)
    {
        Console.WriteLine("MainActivity.初始化");

        // 1. 存下实例
        Instance = this;

        // 2. 注入工厂（解决那个该死的双向依赖）
        Controls.AnimeVideoView.NativeFactory = new AndroidVlcFactory();

        // 3. 先执行初始化再调 base
        LibVLCSharp.Shared.Core.Initialize();

        return base.CustomizeAppBuilder(builder)
            .WithInterFont()
            .With(new FontManagerOptions
            {
                // 2. 设为 null，强迫它走下面的 Fallback 逻辑
                DefaultFamilyName = null,
                FontFallbacks = new[]
            {
                // 3. 直接写系统默认别名，不写 avares 路径，绝对不闪退
                new FontFallback { FontFamily = new FontFamily("sans-serif") }
            }
            });
    }
}
