# alek-dotfiles

Hyprland dotfiles for Fedora 44: Waybar, Fuzzel, Mako, Alacritty, Hypridle and Hyprlock.
Includes desktop scripts, GTK settings and UWSM integration.

- Package versions: `docs/packages.txt`
- Keybindings: `home/.config/hypr/KEYS.txt`
- Fonts: IosevkaTerm Nerd Font Mono, Iosevka Aile and Fira Code

Back up existing settings, then copy `home/` into your home directory:

```sh
cp -a home/. "$HOME/"
```

Adjust `/home/alek` paths and monitor settings. Set `~/.local/share/wallpapers/current`
to a wallpaper image. The power menu requires custom TuneD/LACT profiles.
