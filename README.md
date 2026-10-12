# alek-dotfiles

Portable Hyprland desktop configuration for Fedora 44: Waybar, Fuzzel, Mako,
Alacritty, Hypridle, Hyprlock, GTK settings and UWSM integration. Includes
wallpaper, screenshot, screen recording, session and power profile menus.
The configuration uses Hyprland's Lua API, so the target system needs a
compatible Hyprland release. The installer supports Fedora with DNF5.

- Desktop packages without version pins: `packages.txt`
- Keybindings: `home/.config/hypr/KEYS.txt`
- Fonts: IosevkaTerm Nerd Font Mono, Iosevka Aile and Fira Code
- All helper menus, notifications and launcher entries use English.

## Installation

Run as your regular user on Fedora 44 with DNF5 and sudo:

```sh
./install.sh
```

The installer enables the Hyprland COPR and Terra, installs `packages.txt`,
backs up matching existing files, copies `home/` into your home directory and
applies the GTK interface settings. Home paths are adapted automatically.
File backups are stored under `~/.local/state/alek-dotfiles/backups/`
(or `$XDG_STATE_HOME/alek-dotfiles/backups/`). Matching files are replaced;
existing recording preferences and `~/.config/hypr/local.lua` are preserved.
GTK preferences applied through `gsettings` are not part of the file backup.
The Hyprland COPR is restricted to `hypr*`, `aquamarine*` and `uwsm`.

This repository covers the graphical desktop and its utilities. Installation
does not configure the login manager, install LACT or a power management daemon,
create power profiles, enable power services, or replace GPU drivers. Existing
system power management and any existing LACT installation remain under your
machine's own configuration.

Select the Hyprland UWSM session at login. Set a wallpaper after login:

```sh
desktop-wallpaper /path/to/image.jpg
```

## Machine-specific settings

Displays use their preferred mode with automatic placement. To set a monitor
layout, scaling or a GPU workaround, copy `docs/local.lua.example` to
`~/.config/hypr/local.lua`, edit it, and reload Hyprland. This optional file is
loaded after the shared configuration, is ignored by Git, and is preserved by
the installer. The shared defaults have no fixed output name, refresh rate or
Polaris hardware cursor workaround.

The US/RU keyboard layout and Alt+Shift switching remain desktop preferences;
override `input` in `local.lua` if your keyboard needs different settings.
Keybindings follow upstream dwm with Super as Mod4. Open the reference with Super+F1.

## Appearance and workspaces

The muted Gruvbox palette uses a gray turquoise accent (`#8caaa0`), with a
turquoise-to-mauve (`#b3919e`) active window border at 45 degrees. The accent
also appears in Waybar, Fuzzel, Mako, Hyprlock and capture region selection.

Waybar shows nine workspaces that switch with a left mouse click. A small
outline square in the upper-left corner marks a workspace with windows; the
current occupied workspace has a filled square. Empty workspaces have no square.
The workspace helper uses Hyprland's Lua dispatch API and listens to compositor
events, so it works with releases that no longer accept the legacy workspace
dispatch command. Python and the two SVG indicators are included in the
installation; no additional service is needed.

## Existing power profiles

Super+Shift+P opens the power menu. It uses `powerprofilesctl` when a compatible
power profiles service is already running, otherwise the running TuneD service.
Only profiles reported by that service are offered. Standard and existing custom
TuneD profiles are both supported, with no dependency on `xeon-*`, LACT or AMD
GPU controls. Services are queried without activating a stopped power daemon.
Switching uses the service's normal authorization policy.

```sh
desktop-power-menu --status
desktop-power-menu --list
desktop-power-menu --set balanced
```

`--set` accepts an exact name from `--list`. If neither supported service is
running or its command is unavailable, the menu reports that in English; the
rest of the desktop works independently. Configure your preferred power manager
through your distribution if you want to enable this optional integration.

## Screen recording

- Super+Print: record a region, or stop the current recording.
- Super+Ctrl+Print: record the focused monitor, or stop the current recording.
- Super+Shift+Print: open the English recording settings menu in Fuzzel.
- Recordings are saved in `$(xdg-user-dir VIDEOS)/Recordings`.

The default is software VP8 video with Opus audio in WebM, requiring no specific
GPU device or VA-API driver. New installations use 30 FPS with no audio.
The menu offers microphone, system audio, mixed microphone/system audio and
15/60 FPS. Audio routing uses `pactl` through PipeWire's PulseAudio compatibility
server; temporary mixing modules are removed after recording. Preferences are
stored in `~/.config/desktop-record/settings.json` and preserved on reinstall.
Python is a runtime dependency for the recording, wallpaper and power utilities.

To opt into hardware H.264 in MP4 on a machine with a suitable VA-API driver,
add these lines to `~/.config/uwsm/env-hyprland` and start a new session:

```sh
export DESKTOP_RECORD_ENCODER=vaapi
# Optional: pin a render device instead of wf-recorder's automatic detection.
export DESKTOP_RECORD_DEVICE=/dev/dri/renderD128
```

Hardware H.264 support depends on your GPU and codec packages. The installer
does not configure RPM Fusion or replace GPU drivers. For AMD systems that need
it, configure a suitable driver separately, such as `mesa-va-drivers-freeworld`.
Use `vainfo` to check H.264 encoding support after installing your driver's
utilities. Remove those environment settings to return to software recording.
Encoder options follow [wf-recorder's documentation](https://github.com/ammen99/wf-recorder).
Failure details are written to `~/.local/state/desktop-record/last.log` and
`worker.log` (or under `$XDG_STATE_HOME` when set).

## Verification

Run `python3 -m unittest discover -s tests -v`. The tests mock system commands
and use temporary home directories to verify power service selection, existing
profile handling, recording encoder arguments, backups and repeat installation.
