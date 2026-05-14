using Anime.Avalonia.Controls;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Markup.Xaml;
using Avalonia.Threading;
using LibVLCSharp.Avalonia;
using LibVLCSharp.Shared;
using System;

namespace Anime.Avalonia.Views;

public partial class MainView : UserControl
{
    private LibVLC? _libVLC;
    private MediaPlayer? _mediaPlayer;
    private bool _isDragging = false;

    public MainView()
    {
        InitializeComponent();
    }

    protected override void OnAttachedToVisualTree(VisualTreeAttachmentEventArgs e)
    {
        base.OnAttachedToVisualTree(e);
        _libVLC = new LibVLC();
        _mediaPlayer = new MediaPlayer(_libVLC);
        _mediaPlayer.TimeChanged += MediaPlayer_TimeChanged;
        _mediaPlayer.LengthChanged += MediaPlayer_LengthChanged;

        var container = this.FindControl<Border>("VideoContainer");
        if (container != null && AnimeVideoView.NativeFactory != null)
        {
            var nativeControl = AnimeVideoView.NativeFactory.CreateNativeHost(_mediaPlayer);
            container.Child = nativeControl;
        }
    }

    private void MediaPlayer_TimeChanged(object? sender, MediaPlayerTimeChangedEventArgs e)
    {
        if (_isDragging || _mediaPlayer == null) return;

        Dispatcher.UIThread.Post(() =>
        {
            if (!_isDragging && _mediaPlayer.Length > 0)
            {
                double percent = (double)e.Time / _mediaPlayer.Length * 100;
                VideoProgressBar.Value = percent;
                CurrentTimeText.Text = TimeSpan.FromMilliseconds(e.Time).ToString(@"mm\:ss");
            }
        });
    }

    private void MediaPlayer_LengthChanged(object? sender, MediaPlayerLengthChangedEventArgs e)
    {
        Dispatcher.UIThread.Post(() =>
        {
            TotalTimeText.Text = TimeSpan.FromMilliseconds(e.Length).ToString(@"mm\:ss");
        });
    }

    private void OnPlayButtonClick(object? sender, RoutedEventArgs e)
    {
        if (_mediaPlayer == null) return;

        if (_mediaPlayer.Media == null)
        {
            var media = new Media(_libVLC, new Uri("https://hd.ijycnd.com/play/zbqjD5pd/index.m3u8"));
            _mediaPlayer.Play(media);
            PlayPauseButton.Content = "暂停";
        }
        else
        {
            if (_mediaPlayer.IsPlaying)
            {
                _mediaPlayer.Pause();
                PlayPauseButton.Content = "播放";
            }
            else
            {
                _mediaPlayer.Play();
                PlayPauseButton.Content = "暂停";
            }
        }
    }

    // ==================== 拖拽进度条跳转 ====================
    private void VideoProgressBar_PointerPressed(object sender, PointerPressedEventArgs e)
    {
        if (_mediaPlayer == null || _mediaPlayer.Length <= 0) return;
        _isDragging = true;
        e.Pointer.Capture(VideoProgressBar);
        UpdateUIForDragging(e);
    }

    private void VideoProgressBar_PointerMoved(object sender, PointerEventArgs e)
    {
        if (_isDragging)
        {
            UpdateUIForDragging(e);
        }
    }

    private void VideoProgressBar_PointerReleased(object sender, PointerReleasedEventArgs e)
    {
        if (_isDragging)
        {
            if (_mediaPlayer != null && _mediaPlayer.Length > 0)
            {
                var point = e.GetPosition(VideoProgressBar);
                double ratio = Math.Clamp(point.X / VideoProgressBar.Bounds.Width, 0, 1);
                long targetTime = (long)(_mediaPlayer.Length * ratio);
                _mediaPlayer.SeekTo(TimeSpan.FromMilliseconds(targetTime));
            }
            _isDragging = false;
            e.Pointer.Capture(null);
        }
    }

    private void UpdateUIForDragging(PointerEventArgs e)
    {
        if (_mediaPlayer == null || _mediaPlayer.Length <= 0) return;

        var point = e.GetPosition(VideoProgressBar);
        double ratio = Math.Clamp(point.X / VideoProgressBar.Bounds.Width, 0, 1);
        VideoProgressBar.Value = ratio * 100;

        long previewTime = (long)(_mediaPlayer.Length * ratio);
        CurrentTimeText.Text = TimeSpan.FromMilliseconds(previewTime).ToString(@"mm\:ss");
    }

    protected override void OnDetachedFromVisualTree(VisualTreeAttachmentEventArgs e)
    {
        _mediaPlayer?.Stop();
        _mediaPlayer?.Dispose();
        _libVLC?.Dispose();
        base.OnDetachedFromVisualTree(e);
    }
}