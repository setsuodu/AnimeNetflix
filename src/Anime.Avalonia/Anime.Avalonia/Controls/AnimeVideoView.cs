// 放在共享项目 Anime.Avalonia 中
using Avalonia.Controls;
using LibVLCSharp.Shared;
using System;

namespace Anime.Avalonia.Controls;

// 1. 定义工厂接口
public interface IVlcHostFactory
{
    Control CreateNativeHost(MediaPlayer player);
}

// 2. 播放器控件
public class AnimeVideoView : UserControl
{
    // 静态注入点，由 Android 项目启动时填入
    public static IVlcHostFactory? NativeFactory { get; set; }

    private MediaPlayer? _mediaPlayer;
    public MediaPlayer? MediaPlayer
    {
        get => _mediaPlayer;
        set { _mediaPlayer = value; UpdateView(); }
    }

    private void UpdateView()
    {
        if (_mediaPlayer == null) return;

        if (OperatingSystem.IsWindows())
        {
            // PC 走官方控件（不报错）
            Content = new LibVLCSharp.Avalonia.VideoView { MediaPlayer = _mediaPlayer };
        }
        else if (OperatingSystem.IsAndroid())
        {
            // Android 走注入进来的工厂，完美绕过 Hwnd 依赖
            if (NativeFactory != null)
                Content = NativeFactory.CreateNativeHost(_mediaPlayer);
        }
    }
}