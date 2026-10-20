#!/usr/bin/python3
"""Add desktop files without replacing existing files or changing desktop defaults."""
import argparse
import os
from pathlib import Path, PurePosixPath
import signal
import stat
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
SESSION = Path('/usr/share/wayland-sessions/alek-hyprland.desktop')
PREFERENCES = '.config/desktop-record/settings.json'


def parents(path):
    for directory in reversed(path.parents):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise RuntimeError(f'Unsafe destination directory: {directory}')


def payload(home):
    entries = (REPO / 'docs/install-files.txt').read_text().splitlines()
    if not entries or len(set(entries)) != len(entries):
        raise RuntimeError('Invalid or duplicate installation manifest entries.')
    result = []
    for relative in entries:
        parts = PurePosixPath(relative).parts
        if not parts or relative.startswith('/') or '..' in parts or relative != str(PurePosixPath(relative)):
            raise RuntimeError('Invalid installation manifest path.')
        source = REPO / 'home' / relative
        if source.is_symlink() or not source.is_file() or any(p.is_symlink() for p in source.parents):
            raise RuntimeError(f'Missing regular source file: {relative}')
        data = source.read_bytes().replace(b'/home/alek', os.fsencode(home))
        result.append((home / relative, data, stat.S_IMODE(source.stat().st_mode), relative == PREFERENCES))
    return result


def missing(items):
    result = []
    conflicts = []
    for target, data, mode, preserve in items:
        parents(target)
        if target.is_symlink() or (target.exists() and not target.is_file()):
            conflicts.append(str(target))
        elif target.exists():
            if not preserve and target.read_bytes() != data:
                conflicts.append(str(target))
        else:
            result.append((target, data, mode))
    if conflicts:
        raise RuntimeError('Existing files were preserved. Installation stopped before copying:\n' +
                           '\n'.join(conflicts) + '\nResolve these conflicts manually and run the installer again.')
    return result


def install(items):
    created = []
    directories = []
    try:
        for target, data, mode in items:
            parents(target)
            absent = []
            directory = target.parent
            while not directory.exists():
                absent.append(directory)
                directory = directory.parent
            for directory in reversed(absent):
                try:
                    directory.mkdir()
                    directories.append(directory)
                except FileExistsError:
                    parents(target)
            fd, name = tempfile.mkstemp(prefix='.alek-dotfiles-', dir=target.parent)
            temporary = Path(name)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fchmod(stream.fileno(), mode)
                identity = temporary.stat().st_ino
                # Record ownership before publishing, so interruption can roll back safely.
                created.append((target, identity, data))
                os.link(temporary, target)  # Atomic creation: an existing file is never replaced.
            finally:
                temporary.unlink(missing_ok=True)
    except BaseException:
        for target, identity, data in reversed(created):
            try:
                if not target.is_symlink() and target.stat().st_ino == identity and target.read_bytes() == data:
                    target.unlink()
            except FileNotFoundError:
                pass
        for directory in reversed(directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    return len(created)


def interrupted(signum, frame):
    raise RuntimeError('Installation interrupted; newly created files are being rolled back.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'install', 'check-session', 'install-session'])
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    if args.action.endswith('session'):
        items = [(SESSION, (REPO / 'docs/alek-hyprland.desktop').read_bytes(), 0o644, False)]
    else:
        items = payload(Path.home())
    planned = missing(items)
    if args.action.startswith('install'):
        print(f'Added {install(planned)} files; existing files were preserved.')
    else:
        print(f'Preflight passed: {len(planned)} new files.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
