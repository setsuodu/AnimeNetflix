// 位于 Android 项目
using Android.Views;
using Avalonia.Platform;

namespace Anime.Avalonia.Controls;

public class AndroidControlHandle : IPlatformHandle
{
    private readonly View _view;
    public AndroidControlHandle(View view) => _view = view;

    // Handle 指向 Android 原生视图的句柄
    public System.IntPtr Handle => _view.Handle;
    public string? HandleDescriptor => "AndroidView";

    public void Dispose() => _view.Dispose();
}