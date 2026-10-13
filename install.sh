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

stage=$(mktemp -d)
complete=0
system_started=0
backup=
: > "$stage/changed-files"
: > "$stage/changed-keys"
: > "$stage/created-dirs"
cleanup() {
    result=$?
    trap - EXIT HUP INT TERM
    set +e
    if [ "$complete" -eq 0 ]; then
        rollback_failed=0
        while IFS= read -r relative; do
            target="$HOME/$relative"
            if [ -e "$backup/$relative" ] || [ -L "$backup/$relative" ]; then
                cp -aT --remove-destination "$backup/$relative" "$target" || rollback_failed=1
            else
                rm -f "$target" || rollback_failed=1
            fi
        done < "$stage/changed-files"
        if [ -s "$stage/changed-keys" ]; then
            while IFS= read -r key; do
                gsettings reset org.gnome.desktop.interface "$key" || rollback_failed=1
            done < "$stage/changed-keys"
            dconf load /org/gnome/desktop/interface/ < "$backup/desktop-interface.dconf" || rollback_failed=1
        fi
        while IFS= read -r directory; do
            rmdir "$directory" 2>/dev/null
        done < "$stage/created-dirs"
        if [ "$rollback_failed" -ne 0 ]; then
            printf 'Rollback incomplete. Restore from: %s\n' "$backup" >&2
        fi
        if [ "$system_started" -eq 1 ]; then
            printf '%s\n' 'Installation failed. Completed package and repository changes remain in place.' >&2
        fi
        [ "$result" -ne 0 ] || result=1
    fi
    rm -rf "$stage"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

while IFS= read -r relative; do
    case "$relative" in
        ''|/*|..|../*|*/../*|*/..) printf '%s\n' 'Invalid installation manifest path.' >&2; exit 1 ;;
        .config/hypr/local.lua|.config/uwsm/env-hyprland.local) continue ;;
        .config/desktop-record/settings.json)
            if [ -e "$HOME/$relative" ] || [ -L "$HOME/$relative" ]; then continue; fi ;;
    esac
    source="home/$relative"
    [ -f "$source" ] && [ ! -L "$source" ] || { printf 'Missing regular source file: %s\n' "$source" >&2; exit 1; }
    target="$HOME/$relative"
    [ ! -d "$target" ] || { printf 'Expected a file, found a directory: %s\n' "$target" >&2; exit 1; }
    directory=$(dirname "$target")
    while [ ! -d "$directory" ]; do
        if [ -e "$directory" ] || [ -L "$directory" ]; then
            printf 'Invalid destination directory: %s\n' "$directory" >&2
            exit 1
        fi
        directory=$(dirname "$directory")
    done
    mkdir -p "$stage/home/$(dirname "$relative")"
    cp -aT "$source" "$stage/home/$relative"
done < docs/install-files.txt
install_home=$(printf '%s\n' "$HOME" | sed 's/[\\&|]/\\&/g')
find "$stage/home" -type f -exec sed -i "s|/home/alek|$install_home|g" {} +
find "$stage/home" -type f -print > "$stage/sources"

system_started=1
sudo dnf install -y dnf5-plugins
sudo dnf copr enable -y lionheartp/Hyprland
sudo dnf config-manager setopt 'copr:copr.fedorainfracloud.org:lionheartp:Hyprland.includepkgs=hypr* aquamarine* uwsm xdg-desktop-portal-hyprland'
if ! rpm -q terra-release >/dev/null 2>&1; then
    sudo rpm --import docs/RPM-GPG-KEY-terra44
    sudo dnf install -y --setopt=terra.gpgcheck=1 --repofrompath 'terra,https://repos.fyralabs.com/terra$releasever' terra-release
fi
sudo dnf config-manager setopt terra.priority=200
xargs -r sudo dnf install -y < packages.txt

dconf dump /org/gnome/desktop/interface/ > "$stage/desktop-interface.dconf"
while IFS='=' read -r key value; do
    gsettings get org.gnome.desktop.interface "$key" > /dev/null
    [ "$(gsettings writable org.gnome.desktop.interface "$key")" = true ] || {
        printf 'Interface setting is not writable: %s\n' "$key" >&2
        exit 1
    }
done < docs/desktop-interface.txt

backup_root="${XDG_STATE_HOME:-$HOME/.local/state}/alek-dotfiles/backups"
umask 077
mkdir -p "$backup_root"
backup=$(mktemp -d "$backup_root/$(date +%Y%m%d-%H%M%S)-XXXXXX")
cp "$stage/desktop-interface.dconf" "$backup/desktop-interface.dconf"
while IFS= read -r source; do
    relative=${source#"$stage/home"/}
    target="$HOME/$relative"
    if [ -e "$target" ] || [ -L "$target" ]; then
        mkdir -p "$backup/$(dirname "$relative")"
        cp -aT "$target" "$backup/$relative"
    fi
    directory=$(dirname "$target")
    while [ ! -d "$directory" ]; do
        printf '%s\n' "$directory" >> "$stage/created-dirs"
        directory=$(dirname "$directory")
    done
    mkdir -p "$(dirname "$target")"
    printf '%s\n' "$relative" >> "$stage/changed-files"
    cp -aT --remove-destination "$source" "$target"
done < "$stage/sources"
printf 'Previous settings backed up to: %s\n' "$backup"

while IFS='=' read -r key value; do
    printf '%s\n' "$key" >> "$stage/changed-keys"
    gsettings set org.gnome.desktop.interface "$key" "$value"
done < docs/desktop-interface.txt
complete=1
