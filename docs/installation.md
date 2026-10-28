# Installation details

A configured Hyprland session for **Fedora Workstation 44**, installed alongside
GNOME. Includes Waybar, Fuzzel, Mako, Alacritty, Hypridle, Hyprlock, screenshots,
screen recording, wallpaper and power menus, clipboard history, and desktop application helpers.
The Arthur appearance follows the current desktop: dark gray surfaces, pale text,
a gray-beige accent and a cream focus gradient, with no gaps, rounding, animations,
shadows or blur. Optional GTK, Firefox, Neovim and greeter source files are described in
[`optional/README.md`](../optional/README.md).

## Installation

Run as your regular user on Fedora 44 with DNF5 and sudo:

```sh
./install.sh
```

Before making changes, the installer asks:

1. Use Terra? Default: yes. A no answer skips its installation, key import and
   configuration; `terra*` is disabled only for this installer's DNF commands,
   including when Terra was already configured. Other applications keep their
   repository settings.
2. Install the Arthur login screen from this workstation? Default: no. A yes
   answer builds the bundled gtkgreet-controls RPM, installs greetd/Cage and
   switches the display-manager alias for the next boot. It never stops the
   current login manager or reboots the machine.
3. Use Iosevka or JetBrains Mono? Default: Iosevka with Terra, JetBrains Mono
   without Terra. Iosevka's two packages come from Terra; without Terra they
   must already be installed. JetBrains Mono uses Fedora's
   [`jetbrains-mono-fonts`](https://packages.fedoraproject.org/pkgs/jetbrains-mono-fonts/)
   package. The selected font is applied to Waybar (including the calendar),
   Fuzzel, clipboard menus, Mako, Hyprlock, Alacritty, Zathura and the optional
   greeter. Global GTK settings and existing application configurations are
   preserved; no font packages are removed.

For unattended installation, supply all three answers explicitly:

```sh
./install.sh --terra no --greeter no --font jetbrains-mono
./install.sh --terra yes --greeter yes --font iosevka
```

Missing answers with closed input stop installation before changes. See
`./install.sh --help` for options. The choices are printed before package changes.

Without the optional greeter, log out when convenient and select
**Hyprland (Alek)** in your existing login manager. GNOME remains installed.
The installer does not restart your session.
The new session starts Hyprland through UWSM, which manages environment loading,
Hyprland-only autostarts and session shutdown. `uwsm finalize` completes startup.

The installer:

1. Checks the manifest and existing destinations before making package changes.
2. Enables the Hyprland COPR, optionally enables Terra, and installs the base
   dependencies in `packages.txt` plus the selected font packages.
3. Adds the configuration and scripts listed in `docs/install-files.txt`.
4. Adds `/usr/share/wayland-sessions/alek-hyprland.desktop` as a separate session entry.
5. If selected, installs and configures the greeter as described below.

Existing home files and the session entry are never overwritten. Identical files
are accepted on repeat installation; recording preferences are preserved even when customized.
Conflicting files, symlinks and unsafe destination directories stop installation
with their paths. Resolve conflicts manually and rerun; there is no force option.
Choosing a different font on an existing installation can produce home-file
conflicts; the installer stops before package changes rather than overwriting
customizations. Use the same font for an unchanged repeat installation.
`hypr/local.lua` and `uwsm/env-hyprland.local` are optional, are not installed and
remain untouched. The installer requires the default `~/.config` and
`~/.local/share` locations.

The installer does **not** remove packages, configure GPU drivers or power
daemons, or change GNOME settings. Only selecting the optional greeter replaces
the default display-manager alias and enables a system service. It does not
write global GTK settings,
MIME defaults, Nemo D-Bus overrides or application preferences through dconf.
Application launchers have distinct `alek-hyprland-*` IDs and appear only in
Hyprland. Distribution launchers and existing file associations remain intact.

The COPR is restricted to `hypr*`, `aquamarine*`, `uwsm` and
`xdg-desktop-portal-hyprland`; Terra uses the bundled signing key and lower
repository priority when selected. DNF installs packages and may update required
dependencies
through its normal dependency resolution; the installer never requests erasing,
swapping or removing packages. Package transactions and repository changes are
not rolled back after a later failure. Failed home-file copying rolls back only
files created by that operation; existing or subsequently modified files are
preserved. If adding the session entry fails, the copied home files remain and
a rerun can finish the installation. Forced termination such as SIGKILL cannot
run Python cleanup.

## Optional Arthur greeter

The yes answer explicitly authorizes replacing the current login screen after
reboot. Build dependencies are listed in `docs/greeter-packages.txt`. The bundled,
already-patched source RPM spec is built as the regular user in a temporary
build directory; the resulting RPM is installed through DNF. No source is built
as root. The build directory is removed when installation exits.

Before changing greeter files, the installer creates a root-only backup under
`/var/backups/alek-dotfiles/greeter/before-*/`. It saves any existing
`/etc/greetd/config.toml`, `/etc/greetd/gtkgreet.css`,
`/usr/local/bin/greetd-session/Hyprland`, and the former display-manager symlink
target in `previous-display-manager.json`. The backup path is printed.
The config uses Fedora's packaged `greetd` account instead of depending on the
workstation's custom `greeter` account. Original Arthur colors, the blue Fedora
wordmark, Cage software rendering and the UWSM launcher are retained.

Only after the home payload and session entry are installed successfully does
configuration get replaced. If configuring files or enabling greetd fails, that
operation restores the preceding configuration and display-manager symlink.
SELinux labels are restored with `restorecon` before enabling greetd.
Installed packages and earlier installer steps remain. SIGKILL or power loss
cannot run cleanup. No `systemctl start`, `stop`, or `--now` is used.

To return to GDM on the next boot, when GDM was the previous manager:

```sh
sudo systemctl enable --force gdm.service
```

For another previous manager, use its service name from the saved JSON file.
To restore greetd's previous configuration as well, copy the saved files back
from the backup's `etc/` and `usr/` paths, preserving their permissions and owners.
Files that were previously absent have no saved counterpart.

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
edit it. Hardware settings, LACT profiles and system maintenance files are
outside this repository's installation scope. Greeter configuration is installed
only when explicitly selected.

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
Terra opt-out, font rendering and conflicts, greeter backups and rollback,
non-overwriting installation, GNOME/default preservation, conflicts, repeat
installation, exclusive file creation, rollback, the separate UWSM session,
recording arguments and cleanup, workspace handling, wallpaper recovery and
lock-session selection. They do not install packages on the test host.

