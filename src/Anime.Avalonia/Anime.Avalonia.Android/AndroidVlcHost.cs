// 位于 Android 项目
using Anime.Avalonia.Android;
using Avalonia.Android;
using Avalonia.Platform;
using LibVLCSharp.Shared;
using Avalonia.Controls;

namespace Anime.Avalonia.Controls;

public class AndroidVlcHost : NativeControlHost
{
    private readonly MediaPlayer _player;
    // 明确使用 Android 原生命名空间下的 VideoView
    private LibVLCSharp.Platforms.Android.VideoView? _androidVideoView;

    public AndroidVlcHost(MediaPlayer player) => _player = player;

    protected override IPlatformHandle CreateNativeControlCore(IPlatformHandle parent)
    {
        // 从之前存的静态实例拿 Activity Context
        var context = MainActivity.Instance;
        if (context == null) throw new System.Exception("MainActivity Instance is null!");

        // 实例化 Android 原生 VLC 视图
        _androidVideoView = new LibVLCSharp.Platforms.Android.VideoView(context);
        _androidVideoView.MediaPlayer = _player;

        // 使用刚才定义的 Handle 包装它
        return new AndroidControlHandle(_androidVideoView);
    }

    protected override void DestroyNativeControlCore(IPlatformHandle control)
    {
        _androidVideoView?.Dispose();
        base.DestroyNativeControlCore(control);
    }
}