using Android.App;
using Android.Runtime;
using Avalonia;
using Avalonia.Android;
using System;

namespace Anime.Avalonia.Android
{
    [Application]
    public class Application : AvaloniaAndroidApplication<App>
    {
        protected Application(nint javaReference, JniHandleOwnership transfer) : base(javaReference, transfer)
        {
        }

        protected override AppBuilder CustomizeAppBuilder(AppBuilder builder)
        {
            // === 关键修复：LibVLC 初始化（防止闪退）===
            try
            {
                LibVLCSharp.Shared.Core.Initialize();
                System.Diagnostics.Debug.WriteLine("✅ LibVLCSharp 初始化成功");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"❌ LibVLC 初始化失败: {ex.Message}");
                // 失败也不崩溃，继续启动
            }

            return base.CustomizeAppBuilder(builder)
                .WithInterFont();
        }
    }
}