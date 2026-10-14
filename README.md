# alek-dotfiles

Portable Hyprland desktop configuration for Fedora 44: Waybar, Fuzzel, Mako,
Alacritty, Hypridle, Hyprlock, GTK settings and UWSM integration. Includes
wallpaper, screenshot, screen recording, session and power profile menus,
plus Nemo, Mousepad, Ristretto, Zathura, Xarchiver, MATE Calculator, Disk Usage
Analyzer and Celluloid.
The configuration uses Hyprland's Lua API, so the target system needs a
compatible Hyprland release. The installer requires Fedora 44 with DNF5.

- Desktop packages without version pins: `packages.txt`
- Keybindings: `home/.config/hypr/KEYS.txt`
- Fonts: IosevkaTerm Nerd Font Mono, Iosevka Aile and Adwaita Mono
- All helper menus, notifications and launcher entries use English.

## Installation

Run as your regular user on Fedora 44 with DNF5 and sudo. The installer requires
the default `~/.config` and `~/.local/share` directories; non-default
`XDG_CONFIG_HOME` or `XDG_DATA_HOME` values are rejected before system changes.

```sh
./install.sh
```

The installer validates the source files and destination types, enables the
Hyprland COPR and Terra, installs `packages.txt`, backs up matching existing
files, copies the files listed in `docs/install-files.txt` into your home directory and
applies the GTK interface and application settings. Desktop MIME defaults are merged
into `~/.config/mimeapps.list`; unrelated browser, URI and other associations are retained. Home paths are adapted automatically.
File backups are stored under `~/.local/state/alek-dotfiles/backups/`
(or `$XDG_STATE_HOME/alek-dotfiles/backups/`). Matching files are replaced;
existing recording preferences, `~/.config/hypr/local.lua` and
`~/.config/uwsm/env-hyprland.local` are preserved. The backup also contains
`desktop-interface.dconf`, a snapshot of GTK interface preferences, and
`desktop-applications/`, previous explicit values for the application keys in
`docs/desktop-applications.txt`. Unset application keys are reset on rollback. Terra
bootstrap packages are signature checked using the bundled official Terra 44 key.
The Hyprland COPR is restricted to `hypr*`, `aquamarine*`, `uwsm` and
`xdg-desktop-portal-hyprland`. Ignored and untracked working-directory files
are excluded from the installation payload. Keep `docs/install-files.txt`
in sync with the tracked files under `home/` when adding or removing defaults.

Interface settings are checked and backed up before user files are replaced.
If copying or applying interface settings fails, the installer restores replaced
files, interface and application preferences, removes newly installed files and removes empty
directories it created. Backups remain available; any rollback failure reports
their location. Completed package installations, signing-key imports and system
repository changes remain in place after an error. Those system actions are not
automatically reversed. Forced termination such as SIGKILL cannot run rollback.

This repository covers the graphical desktop and its utilities. Installation
does not configure the login manager, install LACT or a power management daemon,
create power profiles, enable power services, or replace GPU drivers. Existing
system power management and any existing LACT installation remain under your
machine's own configuration.

Select the Hyprland UWSM session at login. Set a wallpaper after login:

```sh
desktop-wallpaper /path/to/image.jpg
```

## Desktop applications

Super+E opens Nemo through an English native Wayland wrapper. FileManager1 and
Nemo D-Bus activation, local launchers and desktop actions use the same wrapper.
Nemo desktop icons are disabled; Open in Terminal uses Alacritty. Mousepad uses
the dark Oblivion scheme and the system monospace font. MATE Calculator opens
floating with History enabled so it can be resized. Audio controls, archive
windows and the GTK portal file chooser open floating and centered. Oversized
floating windows fit the monitor work area on opening, with one delayed check
for initial size negotiation; later manual movement and resizing remain free.

Zathura uses the desktop palette, fits documents to width and supports PDF,
DjVu and comic-book plugins. Ctrl+R toggles page recoloring. Its wrapper expands
local compressed PDFs into temporary files and removes them after the viewer exits.
Ristretto uses ImageMagick to make cached PNG previews for JPEG2000 and XBM;
other supported images open directly. Original image files are preserved.

Nemo has Create Archive, Extract Archive and Extract to New Folder actions using
independent GTK dialogs and 7zip/tar backends. Creation supports ZIP, 7z, tar.gz,
tar.bz2, tar.xz and tar.zst. Extraction skips existing files; new-folder extraction
chooses an unused name. Open encrypted archives in Xarchiver. The separate helper
avoids Xarchiver CLI forwarding errors when its viewer is already open.

GTK3 uses Arc-Dark; GTK2/3/4 use Paper icons by Sam Hewitt and the Adwaita cursor.
Both themes are installed from Fedora packages. GTK4 keeps its dark compatibility
setting; Arc-Dark does not provide a GTK4 theme. The installer adds replacements
and defaults without removing applications already installed on the target machine.

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

Waybar shows nine workspaces that switch with a left mouse click. Color
highlighting distinguishes empty, occupied, active and urgent workspaces.
The workspace helper uses Hyprland's Lua dispatch API and listens to compositor
events, so it works with releases that no longer accept the legacy workspace
dispatch command. The Python helper is included in the installation.
One event observer supplies all nine modules through atomic
snapshots and native Waybar signals. The panel wrapper owns its observer and
cache; existing session autostarts use bounded recovery after failures.
Hypridle reports compositor-confirmed lock transitions to the physical login
session through `desktop-lock-state`. No additional standalone service is needed.

The session menu offers Suspend only when logind reports it as available.
Idle locking and display power management remain independent of system suspend.
GTK settings use Adwaita Sans and Adwaita Mono. The GTK4 dark preference is
retained for plain GTK4 applications; libadwaita may report a compatibility warning.

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
add these lines to `~/.config/uwsm/env-hyprland.local`:

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
The recorder reads this optional file at launch; explicit command environment
settings take precedence. UWSM also loads it when a new session starts.
Encoder options follow [wf-recorder's documentation](https://github.com/ammen99/wf-recorder).
Failure details are written to `~/.local/state/desktop-record/last.log` and
`worker.log` (or under `$XDG_STATE_HOME` when set).

## Verification

Run `python3 -m unittest discover -s tests -v`. The tests mock system commands
and use temporary home directories to verify power service selection, existing
profile handling, recording encoder arguments, backups and repeat installation,
payload filtering, destination preflight and installer rollback (including
termination and failed restoration), MIME merging, application preference rollback,
as well as workspace urgency, PID reuse,
wallpaper rollback and lock-session selection.
These regressions complement physical login, unlock and capture checks; they
do not simulate GPU hardware or certify a cold boot.

The deployed configuration passed a real reboot and login check on 13 October
2026: the five desktop autostarts ran without restarts, the single workspace
observer matched all nine workspaces, the portals started successfully, and
the login keyring was unlocked. Physical password unlock, portal capture and
full recording decode were also checked before that reboot. A fresh installation
on another machine and a power-off/power-on cycle have not been tested.
