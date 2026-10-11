# alek-dotfiles

Hyprland dotfiles for Fedora 44: Waybar, Fuzzel, Mako, Alacritty, Hypridle and Hyprlock.
Includes desktop scripts, GTK settings and UWSM integration.

- Packages without version pins: `packages.txt`
- Keybindings: `home/.config/hypr/KEYS.txt`
- Fonts: IosevkaTerm Nerd Font Mono, Iosevka Aile and Fira Code

Run as your regular user on Fedora 44 with DNF5 and sudo:

```sh
./install.sh
```

The installer enables the Hyprland and LACT COPR repositories and Terra,
installs `packages.txt`, copies `home/` into your home directory and applies
the GTK interface settings. Existing matching files are overwritten;
home paths are adapted automatically. Back up your settings before running it.

This snapshot covers the graphical desktop and its utilities, not all installed
software or system settings. Adjust monitors in `~/.config/hypr/hyprland.lua`,
then select the Hyprland UWSM session at login. Set a wallpaper after login:

```sh
desktop-wallpaper /path/to/image.jpg
```

The power menu expects the machine-specific TuneD/LACT profiles
`xeon-eco`, `xeon-balanced` and `xeon-performance`; they are not included.
Python remains a runtime dependency for the wallpaper and power utilities.
Keybindings follow upstream dwm with Super as Mod4; view the reference with Super+F1.
