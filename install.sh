#!/bin/sh
set -eu

. /etc/os-release
[ "$ID" = fedora ] || { printf '%s\n' 'This installer requires Fedora.' >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || { printf '%s\n' 'Run this installer as your regular user, not root.' >&2; exit 1; }
cd "$(dirname "$0")"

sudo dnf install -y dnf5-plugins
sudo dnf copr enable -y lionheartp/Hyprland
sudo dnf config-manager setopt 'copr:copr.fedorainfracloud.org:lionheartp:Hyprland.includepkgs=hypr* aquamarine* uwsm'
sudo dnf copr enable -y ilyaz/LACT
rpm -q terra-release >/dev/null 2>&1 || sudo dnf install -y --nogpgcheck --repofrompath 'terra,https://repos.fyralabs.com/terra$releasever' terra-release
xargs -r sudo dnf install -y < packages.txt

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT HUP INT TERM
cp -a home/. "$stage/"
install_home=$(printf '%s\n' "$HOME" | sed 's/[\\&|]/\\&/g')
find "$stage" -type f -exec sed -i "s|/home/alek|$install_home|g" {} +
cp -a "$stage"/.[!.]* "$HOME/"

while IFS='=' read -r key value; do
    gsettings set org.gnome.desktop.interface "$key" "$value"
done < docs/desktop-interface.txt
