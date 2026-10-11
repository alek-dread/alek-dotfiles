#!/bin/sh
set -eu

. /etc/os-release
[ "$ID" = fedora ] || { printf '%s\n' 'This installer requires Fedora.' >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || { printf '%s\n' 'Run this installer as your regular user, not root.' >&2; exit 1; }
cd "$(dirname "$0")"

sudo dnf install -y dnf5-plugins
sudo dnf copr enable -y lionheartp/Hyprland
sudo dnf config-manager setopt 'copr:copr.fedorainfracloud.org:lionheartp:Hyprland.includepkgs=hypr* aquamarine* uwsm'
rpm -q terra-release >/dev/null 2>&1 || sudo dnf install -y --nogpgcheck --repofrompath 'terra,https://repos.fyralabs.com/terra$releasever' terra-release
xargs -r sudo dnf install -y < packages.txt

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT HUP INT TERM
cp -a home/. "$stage/"
# Local overrides belong to the target machine, even in a working checkout.
rm -f "$stage/.config/hypr/local.lua"
install_home=$(printf '%s\n' "$HOME" | sed 's/[\\&|]/\\&/g')
find "$stage" -type f -exec sed -i "s|/home/alek|$install_home|g" {} +
# Keep device/audio preferences when installing again on an existing machine.
if [ -e "$HOME/.config/desktop-record/settings.json" ] || [ -L "$HOME/.config/desktop-record/settings.json" ]; then
    rm "$stage/.config/desktop-record/settings.json"
fi

backup_root="${XDG_STATE_HOME:-$HOME/.local/state}/alek-dotfiles/backups"
umask 077
mkdir -p "$backup_root"
backup=$(mktemp -d "$backup_root/$(date +%Y%m%d-%H%M%S)-XXXXXX")
find "$stage" -type f -print | while IFS= read -r source; do
    relative=${source#"$stage"/}
    target="$HOME/$relative"
    if [ -e "$target" ] || [ -L "$target" ]; then
        mkdir -p "$backup/$(dirname "$relative")"
        cp -a "$target" "$backup/$relative"
    fi
    mkdir -p "$(dirname "$target")"
    cp -a --remove-destination "$source" "$target"
done
printf 'Previous settings backed up to: %s\n' "$backup"

while IFS='=' read -r key value; do
    gsettings set org.gnome.desktop.interface "$key" "$value"
done < docs/desktop-interface.txt
