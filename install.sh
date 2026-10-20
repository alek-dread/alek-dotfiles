#!/bin/sh
set -eu

. /etc/os-release
[ "$ID" = fedora ] && [ "${VERSION_ID:-}" = 44 ] || { printf '%s\n' 'This installer requires Fedora 44.' >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || { printf '%s\n' 'Run this installer as your regular user, not root.' >&2; exit 1; }
cd "$(dirname "$0")"
[ "${XDG_CONFIG_HOME:-$HOME/.config}" = "$HOME/.config" ] &&
[ "${XDG_DATA_HOME:-$HOME/.local/share}" = "$HOME/.local/share" ] || {
    printf '%s\n' 'This installer requires the default XDG config and data directories.' >&2
    exit 1
}

# Validate every destination before package/repository changes. Repeat the checks
# immediately before copying; exclusive creation also rejects concurrent conflicts.
python3 docs/install-home.py check
python3 docs/install-home.py check-session
sudo dnf install -y dnf5-plugins
sudo dnf copr enable -y lionheartp/Hyprland
sudo dnf config-manager setopt 'copr:copr.fedorainfracloud.org:lionheartp:Hyprland.includepkgs=hypr* aquamarine* uwsm xdg-desktop-portal-hyprland'
if ! rpm -q terra-release >/dev/null 2>&1; then
    sudo rpm --import docs/RPM-GPG-KEY-terra44
    sudo dnf install -y --setopt=terra.gpgcheck=1 --repofrompath 'terra,https://repos.fyralabs.com/terra$releasever' terra-release
fi
sudo dnf config-manager setopt terra.priority=200
xargs -r sudo dnf install -y < packages.txt
python3 docs/install-home.py install
sudo python3 docs/install-home.py install-session
printf '%s\n' 'Installation complete. At your next login, select Hyprland (Alek). Your existing desktop and login manager remain available.'
