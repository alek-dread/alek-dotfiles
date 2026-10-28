#!/bin/sh
set -eu

terra=
greeter=
font=
usage() {
    printf '%s\n' 'Usage: ./install.sh [--terra yes|no] [--greeter yes|no] [--font iosevka|jetbrains-mono]'
}
while [ "$#" -gt 0 ]; do
    case "$1" in
        --terra|--greeter|--font)
            [ "$#" -ge 2 ] || { usage >&2; exit 1; }
            case "$1" in
                --terra) terra=$2 ;;
                --greeter) greeter=$2 ;;
                --font) font=$2 ;;
            esac
            shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 1 ;;
    esac
done
case "$terra" in ''|yes|no) ;; *) usage >&2; exit 1 ;; esac
case "$greeter" in ''|yes|no) ;; *) usage >&2; exit 1 ;; esac
case "$font" in ''|iosevka|jetbrains-mono) ;; *) usage >&2; exit 1 ;; esac

. /etc/os-release
[ "$ID" = fedora ] && [ "${VERSION_ID:-}" = 44 ] || { printf '%s\n' 'This installer requires Fedora 44.' >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || { printf '%s\n' 'Run this installer as your regular user, not root.' >&2; exit 1; }
cd "$(dirname "$0")"
[ "${XDG_CONFIG_HOME:-$HOME/.config}" = "$HOME/.config" ] &&
[ "${XDG_DATA_HOME:-$HOME/.local/share}" = "$HOME/.local/share" ] || {
    printf '%s\n' 'This installer requires the default XDG config and data directories.' >&2
    exit 1
}

answer() {
    while :; do
        printf '%s ' "$1" >&2
        IFS= read -r reply || { printf '\n%s\n' 'No answer received. Use explicit --terra, --greeter and --font options for unattended installation.' >&2; exit 1; }
        case "$reply" in
            y|Y|yes|YES|д|Д|да|Да) printf yes; return ;;
            n|N|no|NO|н|Н|нет|Нет) printf no; return ;;
            '') printf '%s' "$2"; return ;;
            *) printf '%s\n' 'Ответь да или нет (y/n).' >&2 ;;
        esac
    done
}
if [ -z "$terra" ]; then
    terra=$(answer 'Подключить и использовать репозиторий Terra? [Y/n]' yes)
fi
if [ -z "$greeter" ]; then
    greeter=$(answer 'Установить экран входа Arthur (greetd), заменив текущий после перезагрузки? [y/N]' no)
fi
if [ -z "$font" ]; then
    if [ "$terra" = yes ]; then font_default=1; else font_default=2; fi
    while :; do
        printf 'Шрифт: 1) Iosevka (пакеты Terra), 2) JetBrains Mono. [%s]: ' "$font_default" >&2
        IFS= read -r reply || { printf '\n%s\n' 'No font selected. Use --font for unattended installation.' >&2; exit 1; }
        case "${reply:-$font_default}" in
            1|iosevka)
                if [ "$terra" = no ] && ! rpm -q belleve-invis-iosevka-aile-fonts iosevkaterm-nerd-fonts >/dev/null 2>&1; then
                    printf '%s\n' 'Для Iosevka нужен Terra или уже установленные пакеты шрифта. Выбери JetBrains Mono либо перезапусти установку с Terra.' >&2
                    continue
                fi
                font=iosevka; break ;;
            2|jetbrains-mono) font=jetbrains-mono; break ;;
            *) printf '%s\n' 'Выбери 1 или 2.' >&2 ;;
        esac
    done
fi
if [ "$terra" = no ] && [ "$font" = iosevka ] &&
   ! rpm -q belleve-invis-iosevka-aile-fonts iosevkaterm-nerd-fonts >/dev/null 2>&1; then
    printf '%s\n' 'Iosevka needs Terra or both font packages already installed. Choose --terra yes or --font jetbrains-mono.' >&2
    exit 1
fi
printf 'Terra: %s; greetd: %s; font: %s\n' "$terra" "$greeter" "$font"

# Reject home conflicts before repository or package changes.
python3 docs/install-home.py check --font "$font"
python3 docs/install-home.py check-session
if [ "$greeter" = yes ]; then
    python3 docs/install-greeter.py check --font "$font"
fi
# All DNF operations honor the Terra choice, including existing installations.
# DNF5 rejects an unmatched --disable-repo glob, even on a fresh Fedora install.
disable_terra=no
if [ "$terra" = no ]; then
    disable_terra=$(python3 - <<'PY'
import json
import subprocess

result = subprocess.run(['dnf', 'repo', 'list', '--all', '--json'],
                        capture_output=True, text=True, check=True)
repositories = json.loads(result.stdout)
print('yes' if any(repo['id'].startswith('terra') for repo in repositories) else 'no')
PY
    )
fi
dnf_run() {
    if [ "$disable_terra" = yes ]; then
        sudo dnf '--disable-repo=terra*' "$@"
    else
        sudo dnf "$@"
    fi
}
dnf_run install -y dnf5-plugins
dnf_run copr enable -y lionheartp/Hyprland
dnf_run config-manager setopt 'copr:copr.fedorainfracloud.org:lionheartp:Hyprland.includepkgs=hypr* aquamarine* uwsm xdg-desktop-portal-hyprland'
if [ "$terra" = yes ]; then
    if ! rpm -q terra-release >/dev/null 2>&1; then
        sudo rpm --import docs/RPM-GPG-KEY-terra44
        dnf_run install -y --setopt=terra.gpgcheck=1 --repofrompath 'terra,https://repos.fyralabs.com/terra$releasever' terra-release
    fi
    dnf_run config-manager setopt terra.enabled=1 terra.priority=200
fi
set --
while IFS= read -r package; do
    [ -z "$package" ] || set -- "$@" "$package"
done < packages.txt
if [ "$font" = iosevka ]; then
    set -- "$@" belleve-invis-iosevka-aile-fonts iosevkaterm-nerd-fonts
else
    set -- "$@" jetbrains-mono-fonts
fi
if [ "$greeter" = yes ]; then
    while IFS= read -r package; do
        [ -z "$package" ] || set -- "$@" "$package"
    done < docs/greeter-packages.txt
fi
dnf_run install -y "$@"
if [ "$greeter" = yes ]; then
    greeter_build=$(mktemp -d)
    trap 'rm -rf -- "$greeter_build"' EXIT
    trap 'exit 1' HUP INT TERM
    # Build the bundled, patched source as the regular user.
    rpmbuild -bb optional/greeter/source/gtkgreet-controls.spec \
        --define "_topdir $greeter_build" \
        --define "_sourcedir $PWD/optional/greeter/source"
    dnf_run install -y "$greeter_build"/RPMS/*/gtkgreet-controls-*.rpm
fi
python3 docs/install-home.py install --font "$font"
sudo python3 docs/install-home.py install-session
if [ "$greeter" = yes ]; then
    sudo python3 docs/install-greeter.py install --font "$font"
    printf '%s\n' 'Installation complete. The Arthur greetd screen will be used after reboot. The current session was not stopped.'
else
    printf '%s\n' 'Installation complete. At your next login, select Hyprland (Alek). Your existing login manager remains available.'
fi
