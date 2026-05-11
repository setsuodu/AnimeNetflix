using System;
using System.Collections.Generic;
using System.Text;

using CommunityToolkit.Mvvm.ComponentModel;

namespace MyAvaloniaApp.ViewModels;

public partial class AnimeModel : ObservableObject
{
    [ObservableProperty] private int _id;
    [ObservableProperty] private string _title = string.Empty;
    [ObservableProperty] private string _coverUrl = string.Empty;
    // 可以继续加其他字段，比如 year, tags 等
}