using CommunityToolkit.Mvvm.ComponentModel;

namespace Anime.Avalonia.ViewModels;

public partial class MainViewModel : ViewModelBase
{
    [ObservableProperty]
    private string _greeting = "Welcome to Avalonia!";
}
