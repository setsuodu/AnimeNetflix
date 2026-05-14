using Anime.Avalonia.Controls;
using Avalonia.Controls;
using LibVLCSharp.Shared;

namespace Anime.Avalonia.Desktop;

public class WindowsVlcFactory : IVlcHostFactory
{
    public Control CreateNativeHost(MediaPlayer player)
    {
        // PC 端不需要搞什么 NativeControlHost 手动包装
        // 直接用官方 LibVLCSharp.Avalonia 提供的 VideoView，它是最稳的
        return new LibVLCSharp.Avalonia.VideoView { MediaPlayer = player };
    }
}