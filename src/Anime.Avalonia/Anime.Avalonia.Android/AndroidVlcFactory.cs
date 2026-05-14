// 放在 Android 项目中
using Anime.Avalonia.Controls; // 引用共享项目
using Avalonia.Controls;
using LibVLCSharp.Shared;

namespace Anime.Avalonia.Android;

public class AndroidVlcFactory : IVlcHostFactory
{
    public Control CreateNativeHost(MediaPlayer player)
    {
        return new AndroidVlcHost(player); // 这里就是之前写的那个 NativeControlHost
    }
}