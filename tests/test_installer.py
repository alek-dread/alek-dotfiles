"""Additive installation tests; no packages, greeters or live settings are changed."""
import configparser
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_home', REPO / 'docs/install-home.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class AdditiveInstaller(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        shutil.copytree(REPO, self.repo, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        self.home = self.root / 'home & test'
        self.home.mkdir()
        release = self.root / 'os-release'
        release.write_text('ID=fedora\nVERSION_ID=44\n')
        self.release = release
        self.script = self.repo / 'install.sh'
        self.script.write_text(self.script.read_text().replace('/etc/os-release', str(release)))
        self.session = self.root / 'system/wayland-sessions/alek-hyprland.desktop'
        helper = self.repo / 'docs/install-home.py'
        helper.write_text(helper.read_text().replace('/usr/share/wayland-sessions/alek-hyprland.desktop', str(self.session)))
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.calls = self.root / 'calls.jsonl'
        mock = '''#!/usr/bin/python3
import json, os, subprocess, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['TEST_CALLS'], 'a') as f:
    f.write(json.dumps([name, *args]) + '\\n')
if name == 'id': print('1000')
if name == 'rpm': sys.exit(1)
if name == 'sudo':
    if os.environ.get('FAIL_PACKAGES'): sys.exit(1)
    if args[0] == 'python3': sys.exit(subprocess.run(args).returncode)
if name in ('gsettings', 'dconf', 'systemctl', 'xdg-mime'): sys.exit(99)
'''
        for name in ('sudo', 'rpm', 'id', 'gsettings', 'dconf', 'systemctl', 'xdg-mime'):
            p = self.bin / name
            p.write_text(mock)
            p.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_CONFIG_HOME=str(self.home / '.config'),
                        XDG_DATA_HOME=str(self.home / '.local/share'),
                        PATH=str(self.bin) + ':' + os.environ['PATH'], TEST_CALLS=str(self.calls))

    def run_install(self, options=None, **env):
        if options is None:
            options = ['--terra', 'yes', '--greeter', 'no', '--font', 'iosevka']
        return subprocess.run(['sh', str(self.script), *options], env=dict(self.env, **env),
                              stdin=subprocess.DEVNULL, capture_output=True, text=True)

    def logged(self):
        return [json.loads(s) for s in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def write(self, relative, data):
        p = self.home / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)
        return p

    def test_manifest_matches_tracked_payload_and_has_no_global_overrides(self):
        tracked = subprocess.check_output(['git', 'ls-files', '-z', 'home'], cwd=REPO).decode().split('\0')
        entries = (REPO / 'docs/install-files.txt').read_text().splitlines()
        self.assertEqual(set(entries), {p.removeprefix('home/') for p in tracked if p})
        self.assertEqual(len(entries), len(set(entries)))
        for forbidden in ('.gtkrc-2.0', '.config/mimeapps.list', '.config/uwsm/env'):
            self.assertNotIn(forbidden, entries)
        self.assertFalse(any(p.startswith(('.config/gtk-', '.local/share/dbus-1/', '.config/alacritty/', '.config/zathura/')) for p in entries))
        for p in (REPO / 'home/.local/share/applications').glob('*.desktop'):
            self.assertTrue(p.name.startswith('alek-hyprland-'))
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            parser.read(p)
            self.assertEqual(parser['Desktop Entry']['OnlyShowIn'], 'Hyprland;')

    def test_fresh_workstation_preserves_gnome_defaults_and_adds_uwsm_session(self):
        originals = {}
        for name in ('.config/gtk-3.0/settings.ini', '.config/mimeapps.list', '.config/dconf/user',
                     '.config/alacritty/alacritty.toml', '.config/zathura/zathurarc',
                     '.local/share/applications/nemo.desktop', '.local/share/dbus-1/services/nemo.service'):
            p = self.write(name, 'existing preferences: ' + name)
            p.chmod(0o640)
            originals[p] = (p.read_bytes(), p.stat().st_mode)
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        for p, (content, mode) in originals.items():
            self.assertEqual(p.read_bytes(), content)
            self.assertEqual(p.stat().st_mode, mode)
        self.assertIn('uwsm start -e -D Hyprland hyprland.desktop', self.session.read_text())
        self.assertTrue((self.home / '.local/bin/desktop-terminal').is_file())
        self.assertTrue((self.home / '.config/alek-hyprland/alacritty.toml').is_file())
        calls = self.logged()
        self.assertFalse(any(c[0] in ('gsettings', 'dconf', 'systemctl', 'xdg-mime') for c in calls))
        for call in calls:
            self.assertFalse(any(arg in ('remove', 'swap', '--allowerasing', 'gdm', 'greetd') for arg in call))
        self.assertTrue(any('--setopt=terra.gpgcheck=1' in c for c in calls))
        self.assertTrue(any('wf-recorder' in c for c in calls))

    def test_no_terra_and_jetbrains_never_install_or_configure_terra(self):
        result = self.run_install(['--terra', 'no', '--greeter', 'no', '--font', 'jetbrains-mono'])
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.logged()
        self.assertFalse(any('terra-release' in c or c[:3] == ['sudo', 'rpm', '--import'] for c in calls))
        dnf_calls = [c for c in calls if c[:2] == ['sudo', 'dnf']]
        self.assertTrue(dnf_calls)
        self.assertTrue(all('--disable-repo=terra*' in c for c in dnf_calls))
        self.assertTrue(any('jetbrains-mono-fonts' in c for c in dnf_calls))
        self.assertFalse(any('iosevkaterm-nerd-fonts' in c for c in dnf_calls))
        for relative in ('.config/waybar/style.css', '.config/hypr/hyprlock.conf',
                         '.config/fuzzel/fuzzel.ini', '.config/desktop-clipboard/fuzzel.ini',
                         '.config/mako/config', '.config/alek-hyprland/alacritty.toml',
                         '.config/alek-hyprland/zathura/zathurarc'):
            data = (self.home / relative).read_text()
            self.assertIn('JetBrains Mono', data)
            self.assertNotIn('Iosevka', data)
        self.assertIn('Iosevka', (self.repo / 'home/.config/waybar/style.css').read_text())
        repeated = self.run_install(['--terra', 'no', '--greeter', 'no', '--font', 'jetbrains-mono'])
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertIn('Added 0 files', repeated.stdout)

    def test_missing_answers_never_silently_enable_repositories_or_greeter(self):
        result = self.run_install([])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] == 'sudo' for c in self.logged()))
        self.assertFalse(self.session.exists())

    def test_font_change_conflict_stops_before_packages(self):
        self.assertEqual(self.run_install().returncode, 0)
        self.calls.write_text('')
        result = self.run_install(['--terra', 'no', '--greeter', 'no', '--font', 'jetbrains-mono'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Existing files were preserved', result.stderr)
        self.assertFalse(any(c[0] == 'sudo' for c in self.logged()))

    def test_conflict_stops_before_packages_and_preserves_existing_files(self):
        p = self.write('.config/hypr/hyprland.lua', 'my configuration')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Existing files were preserved', result.stderr)
        self.assertEqual(p.read_text(), 'my configuration')
        self.assertFalse(any(c[0] in ('sudo', 'rpm') for c in self.logged()))
        self.assertFalse((self.home / '.local/bin').exists())

    def test_existing_session_entry_is_not_replaced(self):
        self.session.parent.mkdir(parents=True)
        self.session.write_text('existing session')
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.session.read_text(), 'existing session')
        self.assertFalse(any(c[0] == 'sudo' for c in self.logged()))

    def test_reinstall_preserves_files_preferences_and_optional_overrides(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        preference = self.write('.config/desktop-record/settings.json', '{"audio":"system","fps":60}\n')
        local = self.write('.config/hypr/local.lua', '-- private monitor layout\n')
        env = self.write('.config/uwsm/env-hyprland.local', 'export DESKTOP_RECORD_ENCODER=software\n')
        before = {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns)
                  for p in self.home.rglob('*') if p.is_file()}
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        for p, values in before.items():
            self.assertEqual((p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns), values)
        self.assertIn('Added 0 files', result.stdout)

    def test_ignored_and_untracked_files_never_enter_payload(self):
        junk = self.repo / 'home/.local/bin/untracked-helper'
        junk.write_text('junk')
        self.assertEqual(self.run_install().returncode, 0)
        self.assertFalse((self.home / '.local/bin/untracked-helper').exists())

    def test_symlink_destination_and_parent_are_rejected(self):
        actual = self.root / 'original'
        actual.write_text('keep')
        p = self.home / '.config'
        p.symlink_to(actual)
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual(actual.read_text(), 'keep')
        self.assertFalse(any(c[0] == 'sudo' for c in self.logged()))

    def test_missing_source_stops_before_packages(self):
        (self.repo / 'home/.config/hypr/security.lua').unlink()
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertFalse(any(c[0] == 'sudo' for c in self.logged()))

    def test_package_failure_leaves_home_and_session_untouched(self):
        self.assertNotEqual(self.run_install(FAIL_PACKAGES='1').returncode, 0)
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse(self.session.exists())

    def test_unsupported_os_and_custom_xdg_stop_before_packages(self):
        self.release.write_text('ID=fedora\nVERSION_ID=43\n')
        self.assertNotEqual(self.run_install().returncode, 0)
        self.release.write_text('ID=fedora\nVERSION_ID=44\n')
        self.assertNotEqual(self.run_install(XDG_CONFIG_HOME=str(self.root / 'elsewhere')).returncode, 0)
        self.assertFalse(any(c[0] == 'sudo' for c in self.logged()))


class ExclusiveCopy(unittest.TestCase):
    def test_concurrent_conflict_never_overwrites_and_rolls_back_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / 'new/a'
            b = Path(tmp) / 'new/b'
            real_link = os.link
            def link(source, target):
                if target == b:
                    b.write_bytes(b'concurrent file')
                return real_link(source, target)
            with patch.object(installer.os, 'link', side_effect=link):
                with self.assertRaises(FileExistsError):
                    installer.install([(a, b'a', 0o644), (b, b'b', 0o644)])
            self.assertFalse(a.exists())
            self.assertEqual(b.read_bytes(), b'concurrent file')
            self.assertEqual(sorted(p.name for p in b.parent.iterdir()), ['b'])

    def test_interruption_preserves_subsequently_edited_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / 'new/a'
            b = Path(tmp) / 'new/b'
            real_link = os.link
            def link(source, target):
                if target == b:
                    a.write_bytes(b'edited after installation')
                    raise KeyboardInterrupt()
                return real_link(source, target)
            with patch.object(installer.os, 'link', side_effect=link):
                with self.assertRaises(KeyboardInterrupt):
                    installer.install([(a, b'a', 0o644), (b, b'b', 0o644)])
            self.assertEqual(a.read_bytes(), b'edited after installation')
            self.assertFalse(b.exists())

    def test_failed_copy_removes_only_created_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'new/deep/file'
            with patch.object(installer.os, 'link', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    installer.install([(target, b'data', 0o755)])
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
