# alek-dotfiles

A configured Hyprland session for **Fedora Workstation 44**, installed alongside
GNOME. Includes Waybar, Fuzzel, Mako, Alacritty, Hypridle, Hyprlock, screenshots,
screen recording, wallpaper and power menus, and desktop application helpers.
The Graphite Rhythm appearance follows the current desktop: graphite surfaces,
warm text, gold focus, no gaps, rounding, animations, shadows or blur.

## Installation

Run as your regular user on Fedora 44 with DNF5 and sudo:

```sh
./install.sh
```

Log out when convenient and select **Hyprland (Alek)** in your existing login
manager. GNOME remains available. The installer does not restart your session.
The new session starts Hyprland through UWSM, which manages environment loading,
Hyprland-only autostarts and session shutdown. `uwsm finalize` completes startup.

The installer:

1. Checks the manifest and existing destinations before making package changes.
2. Enables the Hyprland COPR and Terra and installs the dependencies in `packages.txt`.
3. Adds the configuration and scripts listed in `docs/install-files.txt`.
4. Adds `/usr/share/wayland-sessions/alek-hyprland.desktop` as a separate session entry.

Existing files are never overwritten. Identical files are accepted on repeat
installation; recording preferences are preserved even when customized.
Conflicting files, symlinks and unsafe destination directories stop installation
with their paths. Resolve conflicts manually and rerun; there is no force option.
`hypr/local.lua` and `uwsm/env-hyprland.local` are optional, are not installed and
remain untouched. The installer requires the default `~/.config` and
`~/.local/share` locations.

The installer does **not** remove packages, replace GDM or another greeter,
change the default session, configure GPU drivers or power daemons, enable
system services, or change GNOME settings. It does not write global GTK settings,
MIME defaults, Nemo D-Bus overrides or application preferences through dconf.
Application launchers have distinct `alek-hyprland-*` IDs and appear only in
Hyprland. Distribution launchers and existing file associations remain intact.

The COPR is restricted to `hypr*`, `aquamarine*`, `uwsm` and
`xdg-desktop-portal-hyprland`; Terra uses the bundled signing key and lower
repository priority. DNF installs packages and may update required dependencies
through its normal dependency resolution; the installer never requests erasing,
swapping or removing packages. Package transactions and repository changes are
not rolled back after a later failure. Failed home-file copying rolls back only
files created by that operation; existing or subsequently modified files are
preserved. If adding the session entry fails, the copied home files remain and
a rerun can finish the installation. Forced termination such as SIGKILL cannot
run Python cleanup.

## Desktop

- Super+Shift+Enter: configured Alacritty terminal.
- Super+P: application launcher.
- Super+E: Nemo file manager.
- Super+F1: complete key reference.
- Super+Alt+L: lock; Super+Shift+E: session menu.
- Print / Ctrl+Print: region / all-display screenshot.
- Super+Print / Super+Ctrl+Print: region / monitor recording, or stop recording.
- Super+Shift+Print: recording preferences.
- Super+Shift+P: available power profiles.

All menus, notifications and custom launcher entries use English. The keyboard
uses US/RU with Alt+Shift switching. Waybar has nine clickable workspaces and an
event observer compatible with Hyprland's Lua dispatch API. The target system
needs a compatible Lua-based Hyprland release.

The shell uses Iosevka Aile and IosevkaTerm Nerd Font Mono. Hyprland's UWSM
environment selects Adwaita dark and the Adwaita cursor for that session.
GNOME's saved theme, fonts, icons and other application preferences are retained.
Alacritty and Zathura use their own configurations under
`~/.config/alek-hyprland/` through the supplied wrappers, preserving normal
`~/.config/alacritty/` and `~/.config/zathura/` settings.
The design reference is `home/.config/desktop-design/DESIGN.md`.

The desktop starts with a solid graphite background. Choose an image with the
Wallpaper launcher or:

```sh
desktop-wallpaper /path/to/image.jpg
```

Nemo, Mousepad, Ristretto, Zathura, Xarchiver, MATE Calculator, Disk Usage Analyzer
and Celluloid are installed as additional applications. Existing applications
stay installed; your file-opening defaults stay yours. Custom launchers use the
English Wayland wrappers. Zathura supports compressed PDFs with bounded decoding;
Ristretto supports cached JPEG2000/XBM previews with conversion and cache limits.
The supplied Nemo archive actions use independent dialogs and 7zip/tar backends.

## Recording and locking

Recording defaults to software VP8/Opus in WebM, 30 FPS, with no audio. The menu
supports microphone, system audio, both, and 15/30/60 FPS. Recordings are saved
to `$(xdg-user-dir VIDEOS)/Recordings`. Preferences live in
`~/.config/desktop-record/settings.json` and are preserved on repeat installation.

`desktop-record.service` supervises preparation and encoding. `ExecStopPost`
cleans up audio routing even after worker failure. Failed module unloads remain
recorded for retry, and cleanup recovers orphaned recorder mixing modules.
`desktop-lock.service` supervises a single lock process with bounded restarts.
Notifications are hidden while locked. Idle lock is 10 minutes; monitor DPMS is
15 minutes. The supplied idle/session menus do not request system suspend.

Capture permissions allow grim, wf-recorder and the Hyprland portal. Rules take
effect when Hyprland starts. A config reload alone cannot replace permissions.
No AMD-specific cursor or encoder workaround is enabled in the shared config.

VA-API H.264 recording is optional on compatible machines. Put this in
`~/.config/uwsm/env-hyprland.local`:

```sh
export DESKTOP_RECORD_ENCODER=vaapi
# Optional: export DESKTOP_RECORD_DEVICE=/dev/dri/renderD128
```

Codec support depends on your GPU and installed drivers. The installer does not
configure RPM Fusion or replace Mesa packages. Remove the setting to use software
recording; `DESKTOP_RECORD_DISABLE_VAAPI=1` forces software recording if needed.
Failure logs are under `~/.local/state/desktop-record/`.

## Machine preferences

Monitors use preferred modes and automatic placement. For a custom layout or
GPU workaround, copy `docs/local.lua.example` to `~/.config/hypr/local.lua` and
edit it. Hardware settings, LACT profiles, greetd configuration and system
maintenance files are outside this repository's installation scope.

The power menu uses an already-running power-profiles service or TuneD. It lists
only available profiles and does not activate a stopped power daemon:

```sh
desktop-power-menu --status
desktop-power-menu --list
desktop-power-menu --set balanced
```

## Verification

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary homes and mocked package/system commands. They check
non-overwriting installation, GNOME/default preservation, conflicts, repeat
installation, exclusive file creation, rollback, the separate UWSM session,
recording arguments and cleanup, workspace handling, wallpaper recovery and
lock-session selection. They do not install packages on the test host.

The running source desktop passed 22 health checks on 20 October 2026. The
additive installer has automated coverage; a fresh Fedora Workstation VM and a
real GDM login using the new session entry have not been tested.
