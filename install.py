#!/usr/bin/env python3
"""Install the dotfiles, keeping a backup of every replaced file."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import tempfile


def check_destination(path, target):
    """Do not write through symlinks into unrelated directories."""
    for parent in (path.parent, *path.parent.parents):
        if parent == target:
            break
        if parent.is_symlink():
            raise ValueError(f"Destination directory is a symlink: {parent}")
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"Destination directory is not a directory: {parent}")
    if path.is_dir() and not path.is_symlink():
        raise ValueError(f"Destination is a directory: {path}")


def install(args):
    source = Path(__file__).resolve().parent / "home"
    target = args.target.expanduser().resolve()
    if target == source or target.is_relative_to(source):
        raise ValueError("The destination must not be inside the source tree.")
    files = sorted(p for p in source.rglob("*") if p.is_file())
    if not files:
        raise ValueError(f"No dotfiles found in {source}")
    operations = []
    for src in files:
        if src.is_symlink():
            raise ValueError(f"Unexpected source symlink: {src}")
        relative = src.relative_to(source)
        data = src.read_text().replace("/home/alek", str(target)).encode()
        operations.append((relative, data, src.stat().st_mode & 0o777))
    if args.wallpaper:
        wallpaper = args.wallpaper.expanduser().resolve(strict=True)
        if not wallpaper.is_file():
            raise ValueError("Wallpaper must be a file.")
        operations.append((Path(".local/share/wallpapers/current"), wallpaper, None))

    # Validate all destinations before making any changes.
    for relative, _, _ in operations:
        check_destination(target / relative, target)
    backup_root = target / ".local/state/alek-dotfiles/backups"
    check_destination(backup_root / "placeholder", target)
    if args.dry_run:
        for relative, _, _ in operations:
            print(f"Would install: {target / relative}")
        print("No files changed.")
        return

    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-")
    backup = Path(tempfile.mkdtemp(prefix=stamp, dir=backup_root))
    print(f"Backup: {backup}", flush=True)
    # Finish backing up all existing destinations before replacing any of them.
    for relative, _, _ in operations:
        destination = target / relative
        if destination.exists() or destination.is_symlink():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, saved, follow_symlinks=False)

    for relative, data, mode in operations:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".alek-dotfiles-", dir=destination.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                if mode is not None:
                    stream.write(data)
            if mode is None:
                temporary.unlink()
                temporary.symlink_to(data)
            else:
                temporary.chmod(mode)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    print(f"Installed {len(operations)} files into {target}")
    if not (target / ".local/share/wallpapers/current").exists():
        print("Set a wallpaper with: ./install.py --wallpaper /path/to/image.jpg")
    print("Packages and fonts must be installed separately. Log into Hyprland with UWSM.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview without writing files")
    parser.add_argument("--wallpaper", type=Path, help="set the wallpaper image symlink")
    parser.add_argument("--target", type=Path, default=Path.home(), help="destination home directory")
    args = parser.parse_args()
    try:
        install(args)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Install failed: {error}\n")


if __name__ == "__main__":
    main()
