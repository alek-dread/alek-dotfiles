# alek-dotfiles

Hyprland dotfiles for Fedora 44: Waybar, Fuzzel, Mako, Alacritty, Hypridle and Hyprlock.
Includes desktop scripts, GTK settings and UWSM integration.

- Package versions: `docs/packages.txt`
- Keybindings: `home/.config/hypr/KEYS.txt`
- Fonts: IosevkaTerm Nerd Font Mono, Iosevka Aile and Fira Code

Install with Python 3 (existing files are backed up automatically):

```sh
./install.py --dry-run
./install.py --wallpaper /path/to/image.jpg
```

Home paths are adapted automatically. Backups: `~/.local/state/alek-dotfiles/backups/`.
The wallpaper option is optional. Install packages and fonts separately, adjust monitor
settings, then log into Hyprland with UWSM. The power menu requires custom TuneD/LACT profiles.
