# Installation details

A configured Hyprland session for **Fedora Workstation 44**, installed alongside
GNOME. Includes Waybar, Fuzzel, Mako, Alacritty, Hypridle, Hyprlock, screenshots,
screen recording, wallpaper and power menus, clipboard history, and desktop application helpers.
The Arthur appearance follows the current desktop: dark gray surfaces, pale text,
a gray-beige accent and a cream focus gradient, with no gaps, rounding, animations,
shadows or blur. Optional GTK, Firefox, Neovim and greeter files are described in
[`optional/README.md`](../optional/README.md).

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

## Clipboard history

See [clipboard.md](clipboard.md) for shortcuts, storage limits and activation.
The installer adds the files without enabling history recording automatically.

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

