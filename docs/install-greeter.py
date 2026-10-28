#!/usr/bin/python3
"""Install the optional greeter with backups and defer activation until next boot."""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import stat
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
BACKUPS = Path('/var/backups/alek-dotfiles/greeter')
DISPLAY_MANAGER = Path('/etc/systemd/system/display-manager.service')
TARGETS = (
    ('etc/greetd/config.toml', 0o644),
    ('etc/greetd/gtkgreet.css', 0o644),
    ('usr/local/bin/greetd-session/Hyprland', 0o755),
)


def safe_parents(path):
    for parent in path.parents:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise RuntimeError(f'Unsafe destination directory: {parent}')


def payload(font):
    result = []
    for relative, mode in TARGETS:
        source = REPO / 'optional/greeter' / relative
        if source.is_symlink() or not source.is_file():
            raise RuntimeError(f'Missing regular greeter source: {source}')
        data = source.read_bytes()
        if relative.endswith('config.toml'):
            # Use the service account supplied by Fedora's greetd package.
            data = data.replace(b'user = "greeter"', b'user = "greetd"')
        if font == 'jetbrains-mono' and relative.endswith('.css'):
            data = data.replace(b'Iosevka Aile', b'JetBrains Mono')
        target = Path('/') / relative
        safe_parents(target)
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise RuntimeError(f'Unsafe greeter destination: {target}')
        result.append((target, data, mode))
    safe_parents(DISPLAY_MANAGER)
    if DISPLAY_MANAGER.exists() and not DISPLAY_MANAGER.is_symlink():
        raise RuntimeError(f'Expected a display-manager symlink: {DISPLAY_MANAGER}')
    return result


def atomic_write(target, data, mode, uid=0, gid=0):
    safe_parents(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.alek-greeter-', dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), uid, gid)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def configure(items):
    safe_parents(BACKUPS / 'backup')
    BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = Path(tempfile.mkdtemp(prefix='before-', dir=BACKUPS))
    previous_manager = os.readlink(DISPLAY_MANAGER) if DISPLAY_MANAGER.is_symlink() else None
    original = {}
    # Finish every backup before replacing any configuration file.
    for target, _, _ in items:
        if target.exists():
            info = target.stat()
            original[target] = (target.read_bytes(), stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid)
            saved = backup / target.relative_to('/')
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            os.chown(saved, info.st_uid, info.st_gid)
        else:
            original[target] = None
    (backup / 'previous-display-manager.json').write_text(json.dumps(previous_manager) + '\n')
    changed = []
    try:
        for target, data, mode in items:
            # Record before publication so interruption cannot omit a changed file.
            changed.append(target)
            atomic_write(target, data, mode)
        subprocess.run(['restorecon', '-RF', '/etc/greetd',
                        '/usr/local/bin/greetd-session'], check=True)
        # No --now: replacing the alias must not stop the current display manager.
        subprocess.run(['systemctl', 'enable', '--force', 'greetd.service'], check=True)
    except BaseException:
        for target in reversed(changed):
            before = original[target]
            if before is None:
                target.unlink(missing_ok=True)
            else:
                atomic_write(target, *before)
        # Restore the prior boot selection if systemctl changed the alias then failed.
        if DISPLAY_MANAGER.is_symlink():
            DISPLAY_MANAGER.unlink()
        if previous_manager is not None:
            DISPLAY_MANAGER.symlink_to(previous_manager)
        subprocess.run(['systemctl', 'daemon-reload'], check=False)
        raise
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'install'])
    parser.add_argument('--font', choices=['iosevka', 'jetbrains-mono'], required=True)
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise RuntimeError('Greeter installation interrupted; restoring configuration.')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    items = payload(args.font)
    if args.action == 'check':
        for filename in ('gtkgreet-controls.spec', 'gtkgreet-controls-0.8.20261017.tar.xz'):
            source = REPO / 'optional/greeter/source' / filename
            if source.is_symlink() or not source.is_file():
                raise RuntimeError(f'Missing regular greeter build input: {source}')
        print('Greeter preflight passed; existing files will be backed up.')
        return
    if os.geteuid() != 0:
        raise RuntimeError('Greeter installation requires root.')
    pwd.getpwnam('greetd')
    for binary in ('gtkgreet-controls', 'cage', 'dbus-run-session', 'uwsm'):
        if not (Path('/usr/bin') / binary).is_file():
            raise RuntimeError(f'Missing installed greeter dependency: {binary}')
    backup = configure(items)
    print(f'Greeter configured for next boot. Backup: {backup}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
