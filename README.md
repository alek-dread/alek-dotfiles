# alek-dotfiles

Hyprland dotfiles for Fedora 44: Waybar, Fuzzel, Mako, Alacritty, Hypridle and Hyprlock.
Includes desktop scripts, screen recording, GTK settings and UWSM integration.

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
The Hyprland COPR is restricted to `hypr*`, `aquamarine*` and `uwsm`, matching
the current desktop setup.

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

Screen recording uses `wf-recorder` with H.264 VA-API on `/dev/dri/renderD128`:

- Super+Print: record a region, or stop the current recording.
- Super+Ctrl+Print: record the focused monitor, or stop the current recording.
- Super+Shift+Print: open the English recording settings menu in Fuzzel.
- Recordings are saved as MP4 in `$(xdg-user-dir VIDEOS)/Recordings`.

The saved settings select the default microphone at 30 FPS. The menu also offers
no audio, system audio, mixed microphone/system audio and 15/60 FPS. Audio routing
uses `pactl` through PipeWire's PulseAudio compatibility server; temporary mixing
modules are removed after recording. Recording settings are stored in
`~/.config/desktop-record/settings.json` and are overwritten by installation.

Hardware encoding requires a GPU and VA-API driver with H.264 encoding support.
The current AMD setup uses RPM Fusion's `mesa-va-drivers-freeworld`; the installer
does not configure RPM Fusion or replace GPU drivers. On a new machine, configure
the appropriate driver first and check `vainfo` for an H.264 encoding entrypoint.
Adjust the render device in `desktop-record` if your GPU uses a different path.
Failure details are written to `~/.local/state/desktop-record/last.log` and
`worker.log` (or under `$XDG_STATE_HOME` when set).
