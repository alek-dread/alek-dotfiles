"""Installer failure regressions with isolated homes and mocked system commands."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class InstallerFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        shutil.copytree(REPO, self.repo, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        release = self.root / 'os-release'
        release.write_text('ID=fedora\nVERSION_ID=44\n')
        self.script = self.repo / 'install.sh'
        self.script.write_text(self.script.read_text().replace('/etc/os-release', str(release)))
        self.home = self.root / 'home'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.calls = self.root / 'calls.jsonl'
        self.prefs = self.root / 'prefs.json'
        self.original_prefs = {'gtk-theme': "'previous-theme'", 'cursor-size': '32'}
        self.prefs.write_text(json.dumps(self.original_prefs))
        mock = '''#!/usr/bin/python3
import json, os, signal, subprocess, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['TEST_CALLS'], 'a') as f:
    f.write(json.dumps([name, *args]) + '\\n')
prefs = Path(os.environ['TEST_PREFS'])
if name == 'id': print('1000')
if name == 'rpm': sys.exit(1)
if name == 'sudo' and os.environ.get('FAIL_PACKAGES'): sys.exit(1)
if name == 'dconf':
    if args[0] == 'dump':
        if os.environ.get('FAIL_DUMP'): sys.exit(1)
        print(prefs.read_text())
    if args[0] == 'load': prefs.write_text(sys.stdin.read())
if name == 'gsettings':
    state = json.loads(prefs.read_text())
    if args[0] == 'writable': print('false' if os.environ.get('READ_ONLY') else 'true')
    if args[0] == 'get': print(state.get(args[2], 'default'))
    if args[0] == 'set':
        state[args[2]] = args[3]
        prefs.write_text(json.dumps(state))
        if os.environ.get('FAIL_SETTING') == args[2]: sys.exit(1)
        if os.environ.get('SIGNAL_SETTING') == args[2]: os.kill(os.getppid(), signal.SIGTERM)
    if args[0] == 'reset':
        state.pop(args[2], None)
        prefs.write_text(json.dumps(state))
if name == 'cp':
    if os.environ.get('FAIL_RESTORE') and '/backups/' in args[-2]: sys.exit(1)
    result = subprocess.run(['/usr/bin/cp', *args]).returncode
    if os.environ.get('FAIL_COPY') and '/home/.local/bin/desktop-bar' in args[-2]:
        if '--remove-destination' in args: sys.exit(1)
    sys.exit(result)
'''
        for name in ('sudo', 'rpm', 'id', 'gsettings', 'dconf', 'cp'):
            path = self.bin / name
            path.write_text(mock)
            path.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_STATE_HOME=str(self.home / '.local/state'),
                        XDG_CONFIG_HOME=str(self.home / '.config'),
                        XDG_DATA_HOME=str(self.home / '.local/share'),
                        PATH=str(self.bin) + ':' + os.environ['PATH'],
                        TEST_CALLS=str(self.calls), TEST_PREFS=str(self.prefs))

    def run_install(self, **env):
        return subprocess.run(['sh', str(self.script)], env=dict(self.env, **env),
                              capture_output=True, text=True)

    def write_old_config(self):
        path = self.home / '.config/alacritty/alacritty.toml'
        path.parent.mkdir(parents=True)
        path.write_text('previous configuration\n')
        path.chmod(0o640)
        return path

    def assert_no_system_calls(self):
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []
        self.assertFalse(any(call[0] in ('sudo', 'rpm', 'gsettings', 'dconf') for call in calls))

    def test_manifest_matches_tracked_payload(self):
        tracked = subprocess.check_output(['git', 'ls-files', '-z', 'home'], cwd=REPO).decode().split('\0')
        expected = {path.removeprefix('home/') for path in tracked if path}
        entries = (REPO / 'docs/install-files.txt').read_text().splitlines()
        self.assertEqual(len(entries), len(set(entries)))
        self.assertEqual(set(entries), expected)

    def test_ignored_and_untracked_files_are_never_installed(self):
        for name in ('audit-junk.bak', '__pycache__/junk.pyc', 'untracked-helper'):
            path = self.repo / 'home/.local/bin' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'junk\x00/home/alek')
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('audit-junk.bak', '__pycache__', 'untracked-helper'):
            self.assertFalse((self.home / '.local/bin' / name).exists())
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertTrue(any('xdg-desktop-portal-hyprland' in arg and 'includepkgs=' in arg
                            for call in calls for arg in call))

    def test_destination_directory_rejected_before_system_changes(self):
        target = self.home / '.config/alacritty/alacritty.toml'
        target.mkdir(parents=True)
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('found a directory', result.stderr)
        self.assertEqual(list(target.iterdir()), [])
        self.assert_no_system_calls()

    def test_parent_file_rejected_before_system_changes(self):
        (self.home / '.config').write_text('keep')
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertEqual((self.home / '.config').read_text(), 'keep')
        self.assert_no_system_calls()

    def test_custom_xdg_directories_rejected_before_system_changes(self):
        for key in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME'):
            with self.subTest(key=key):
                self.assertNotEqual(self.run_install(**{key: str(self.root / 'custom')}).returncode, 0)
                self.assert_no_system_calls()

    def test_missing_manifest_source_rejected_before_system_changes(self):
        (self.repo / 'home/.config/alacritty/alacritty.toml').unlink()
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assert_no_system_calls()

    def test_failed_dconf_snapshot_does_not_replace_files(self):
        old = self.write_old_config()
        self.assertNotEqual(self.run_install(FAIL_DUMP='1').returncode, 0)
        self.assertEqual(old.read_text(), 'previous configuration\n')
        self.assertFalse((self.home / '.local/bin').exists())

    def test_readonly_settings_do_not_replace_files(self):
        old = self.write_old_config()
        self.assertNotEqual(self.run_install(READ_ONLY='1').returncode, 0)
        self.assertEqual(old.read_text(), 'previous configuration\n')
        self.assertFalse((self.home / '.local/bin').exists())

    def test_setting_failure_restores_files_modes_preferences_and_directories(self):
        old = self.write_old_config()
        result = self.run_install(FAIL_SETTING='cursor-size')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(old.read_text(), 'previous configuration\n')
        self.assertEqual(old.stat().st_mode & 0o777, 0o640)
        self.assertEqual(json.loads(self.prefs.read_text()), self.original_prefs)
        self.assertFalse((self.home / '.local/bin').exists())
        self.assertFalse((self.home / '.config/hypr').exists())
        self.assertIn('package and repository changes remain', result.stderr)

    def test_copy_failure_restores_original_symlink(self):
        old = self.write_old_config()
        actual = self.root / 'actual-config'
        old.replace(actual)
        old.symlink_to(actual)
        result = self.run_install(FAIL_COPY='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(old.is_symlink())
        self.assertEqual(old.resolve(), actual)
        self.assertEqual(actual.read_text(), 'previous configuration\n')
        self.assertFalse((self.home / '.local/bin').exists())

    def test_package_failure_leaves_home_untouched(self):
        result = self.run_install(FAIL_PACKAGES='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_termination_restores_files_and_preferences(self):
        old = self.write_old_config()
        result = self.run_install(SIGNAL_SETTING='cursor-size')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(old.read_text(), 'previous configuration\n')
        self.assertEqual(json.loads(self.prefs.read_text()), self.original_prefs)
        self.assertFalse((self.home / '.local/bin').exists())

    def test_failed_restore_reports_retained_backup(self):
        self.write_old_config()
        result = self.run_install(FAIL_SETTING='cursor-size', FAIL_RESTORE='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Rollback incomplete. Restore from:', result.stderr)
        backups = list((self.home / '.local/state/alek-dotfiles/backups').iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / '.config/alacritty/alacritty.toml').read_text(),
                         'previous configuration\n')
